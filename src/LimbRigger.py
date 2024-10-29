import maya.cmds as mc 
import maya.OpenMayaUI as omui
import maya.mel as mel
from maya.OpenMaya import MVector
from PySide2.QtWidgets import QWidget, QMainWindow, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit, QSlider
from PySide2.QtCore import Qt
from shiboken2 import wrapInstance

class LimbRiggerWidget(QWidget): #This class has everything weve been working on.
    def __init__(self):
        mayaMainWindow = LimbRiggerWidget.GetMayaMainWindow() # First thing we do is figure out maya main window and if theres any existing windows we remove it so that we only have ou unique one.

        for existing in mayaMainWindow.findChildren(QWidget, LimbRiggerWidget.GetWindowUniqueId()): #-->
            existing.deleteLater() #-->

        super().__init__(parent=mayaMainWindow) # set the parent to be the maya window
        self.setWindowTitle("Limb Rigger") #set the window title
        self.setWindowFlags(Qt.Window) #make it a window
        self.setObjectName(LimbRiggerWidget.GetWindowUniqueId()) # amkes sure it has an ID

        self.controllerSize = 10 # This restores the controller size 
        self.masterLayout = QVBoxLayout() # This is the master layout
        self.setLayout(self.masterLayout) #-->

        self.masterLayout.addWidget(QLabel("Please Select the Root, Middle, and End joint of the limb (in order):")) # This is adding out Labels

        ctrlSizeLayout = QHBoxLayout()
        self.masterLayout.addLayout(ctrlSizeLayout)

        ctrlSizeLayout.addWidget(QLabel("ControllerSize: ")) # This give us our slider and controls the size of the controller 
        ctrlSizeSlider = QSlider() #-->
        ctrlSizeSlider.setOrientation(Qt.Horizontal) #-->
        ctrlSizeSlider.setValue(self.controllerSize) #-->
        ctrlSizeSlider.setMinimum(1) #-->
        ctrlSizeSlider.setMaximum(30)#-->
        ctrlSizeLayout.addWidget(ctrlSizeSlider) #-->

        self.ctrlSizeLabel = QLabel(str(self.controllerSize)) #This shows the sliders value
        ctrlSizeLayout.addWidget(self.ctrlSizeLabel) #-->
        ctrlSizeSlider.valueChanged.connect(self.ControllerSizeUpdated) #-->

        buildLimbRigBtn = QPushButton("Build") # Builds our Button that allows us to click to build
        buildLimbRigBtn.clicked.connect(self.BuildRig)#-->
        self.masterLayout.addWidget(buildLimbRigBtn) #-->

    def BuildRig(self):
        selection = mc.ls(sl =True) # This picks out the slection to be the joints.

        rootJnt = selection[0] #-->
        midJnt = selection[1] #-->
        endJnt = selection[2] #-->

        rootCtrl, rootCtrlGrp = self.CreateFKCtrlForJnt(rootJnt) #Creates the IK Controller
        midCtrl, midCtrlGrp = self.CreateFKCtrlForJnt(midJnt) #-->
        endCtrl, endCtrlGrp = self.CreateFKCtrlForJnt(endJnt) #-->


        mc.parent(endCtrlGrp, midCtrl) # This is putting them into the correct hierarchy 
        mc.parent(midCtrlGrp, rootCtrl) #-->

        ikEndCtrlName, ikEndCtrlGrpName, poleVectorCtrlName, poleVectorCtrlGrpName, ikHanleName = self.BuildIkControls(rootJnt, midJnt, endJnt) # Builds our controls.

        ikfkBlendCtrlName = "ac_ikfk_blend_" + rootJnt # Creates our custom curve (cube we made) for the ik/fk blend control and groups it
        ikfkBlendCtrlGrpName = ikfkBlendCtrlName + "_grp" #-->
        
        mel.eval(f"curve -d 1 -n {ikfkBlendCtrlName} -p -1 2 0 -p 1 2 0 -p 1 0 0 -p 3 0 0 -p 3 -2 0 -p 1 -2 0 -p 1 -4 0 -p -1 -4 0 -p -1 -2 0 -p -3 -2 0 -p -3 0 0 -p -1 0 0 -p -1 2 0 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 ;")
        mc.group(ikfkBlendCtrlName, n = ikfkBlendCtrlGrpName) #-->

        rootJntPos = mc.xform(rootJnt, q=True, ws=True, t=True) # Positions the IK/FK blend control near the root joint and adds an attribute(sllider) for blending between IK and FK
        print(ikfkBlendCtrlGrpName) #-->
        mc.move(rootJntPos[0]*2, rootJntPos[1], rootJntPos[2], ikfkBlendCtrlName) #-->

        ikfkBlendAttr = "ikfkBlend" #-->
        mc.addAttr(ikfkBlendCtrlName, ln=ikfkBlendAttr, k=True, min=0, max=1) #--> (slider)

        endJntOrientConstraint = mc.listConnections(endJnt, s=True, type = "orientConstraint")[0] # Uses expressions to connect the visibility and blending of IK and FK controls based on the IK/FK blend attribute(slider)
        
        mc.expression(s=f"{rootCtrlGrp}.v=1-{ikfkBlendCtrlName}.{ikfkBlendAttr}") #-->
        mc.expression(s=f"{ikEndCtrlGrpName}.v={ikfkBlendCtrlName}.{ikfkBlendAttr}") #-->
        mc.expression(s=f"{poleVectorCtrlGrpName}.v={ikfkBlendCtrlName}.{ikfkBlendAttr}") #-->
        mc.expression(s=f"{ikHanleName}.ikBlend={ikfkBlendCtrlName}.{ikfkBlendAttr}") #-->
        mc.expression(s=f"{endJntOrientConstraint}.{endCtrl}W0=1-{ikfkBlendCtrlName}.{ikfkBlendAttr}") #-->
        mc.expression(s=f"{endJntOrientConstraint}.{ikEndCtrlName}W1={ikfkBlendCtrlName}.{ikfkBlendAttr}") #-->

        topGrpName = rootJnt + "_rig_grp" # Groups all the rig controls into a single group so its organized
        mc.group([ikEndCtrlGrpName, poleVectorCtrlGrpName, rootCtrlGrp, ikfkBlendCtrlGrpName], n = topGrpName) #-->


    def BuildIkControls(self, rootJnt, midJnt, endJnt):
        # Creates End Conroler, draws the controller curve, scales and freezes it, groups and matches to end joint, and constrains joints orientation to the controller
        endCtrlName = "a_ik" + endJnt #-->
        endCtrlGrpName = endCtrlName + "_grp" #-->
        mel.eval(f"curve -d 1 -n {endCtrlName} -p -0.5 0.5 0.5 -p -0.5 0.5 -0.5 -p -0.5 -0.5 -0.5 -p -0.5 -0.5 0.5 -p -0.5 0.5 0.5 -p 0.5 0.5 0.5 -p 0.5 -0.5 0.5 -p -0.5 -0.5 0.5 -p -0.5 -0.5 -0.5 -p 0.5 -0.5 -0.5 -p 0.5 0.5 -0.5 -p -0.5 0.5 -0.5 -p -0.5 0.5 0.5 -p 0.5 0.5 0.5 -p 0.5 0.5 -0.5 -p 0.5 -0.5 -0.5 -p 0.5 -0.5 0.5 -p 0.5 0.5 0.5 -k 0 -k 1 -k 2 -k 3 -k 4 -k 5 -k 6 -k 7 -k 8 -k 9 -k 10 -k 11 -k 12 -k 13 -k 14 -k 15 -k 16 -k 17 ;")
        mc.scale(self.controllerSize, self.controllerSize, self.controllerSize, endCtrlName, r=True) #-->
        mc.makeIdentity(endCtrlName, apply = True) # freeze transforms #-->
        mc.group(endCtrlName, n = endCtrlGrpName) #-->
        mc.matchTransform(endCtrlGrpName, endJnt) #-->
        mc.orientConstraint(endCtrlName, endJnt) #-->



        #ikHandle
        ikHanleName = "ikHandle_" + endJnt # Creates name for IK Handle name and IK itself from root to end joint. 
        mc.ikHandle(n=ikHanleName, sj = rootJnt, ee = endJnt, sol = "ikRPsolver") #-->

        #get(q=True) the world space(ws=True) translation(t=True) of the root joint, returns a list of 3 values [x, y, z]

        #Calculates the Pole vector postions
        rootJntPosVals = mc.xform(rootJnt, q=True, ws=True, t=True) #-->
        rootJntPos = MVector(rootJntPosVals[0], rootJntPosVals[1], rootJntPosVals[2]) #-->

        endJntPosVals = mc.xform(endJnt, q=True, ws=True, t=True) #-->
        endJntPos = MVector(endJntPosVals[0], endJntPosVals[1], endJntPosVals[2]) #-->

        poleVectorVals = mc.getAttr(ikHanleName+".poleVector")[0] #-->
        poleVector = MVector(poleVectorVals[0], poleVectorVals[1], poleVectorVals[2]) #-->

        rootToEndVector = endJntPos - rootJntPos #-->
        limbDirOffset = rootToEndVector/2 #-->

        poleVector.normalize() #-->
        poleVectorOffset = poleVector * rootToEndVector.length() #-->

        poleVectorCtrlPos = rootJntPos + limbDirOffset + poleVectorOffset #-->

        poleVectorCtrlName = "ac_ik" + midJnt #Creates our Pole Vector, Naming, Positioning, and Constraints 
        poleVectorCtrlGrpName = poleVectorCtrlName + "_grp" #-->
        mc.spaceLocator(n=poleVectorCtrlName) #-->
        mc.group(poleVectorCtrlName, n = poleVectorCtrlGrpName) #-->
        mc.move(poleVectorCtrlPos[0], poleVectorCtrlPos[1], poleVectorCtrlPos[2], poleVectorCtrlGrpName) #-->

        mc.poleVectorConstraint(poleVectorCtrlName, ikHanleName) #-->
        mc.parent(ikHanleName, endCtrlName)  #Parents the IK handle to the end controller for better control

        return endCtrlName, endCtrlGrpName, poleVectorCtrlName, poleVectorCtrlGrpName, ikHanleName

    def CreateFKCtrlForJnt(self, jnt): # Creates FK for a given joint, names it, creates a circle control, groups it, matches transforms, and Constrains it to follow rotation of the control.
        ctrlName = "ac_fk_" + jnt #-->
        ctrlGrpName = ctrlName + "grp" #-->
        mc.circle(n=ctrlName, r=self.controllerSize, nr=(1,0,0)) #-->
        mc.group(ctrlName, n = ctrlGrpName) #-->
        mc.matchTransform(ctrlGrpName, jnt) #-->
        mc.orientConstraint(ctrlName, jnt) #-->
        return ctrlName, ctrlGrpName #-->

    def ControllerSizeUpdated(self, newSize): # Updates Controller Size, so updates size and updates label to show new size.
        self.controllerSize = newSize #-->
        self.ctrlSizeLabel.setText(str(newSize)) #-->


    @staticmethod # retrieves our Maya window for our custom UI's
    def GetMayaMainWindow():
        mayaMainWindow = omui.MQtUtil.mainWindow()
        return wrapInstance(int(mayaMainWindow), QMainWindow)

    @staticmethod
    def GetWindowUniqueId():
        return "sdkjhkjhkjhkj"

def Run():
    LimbRiggerWidget().show()