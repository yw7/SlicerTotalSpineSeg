import logging
import os
import re
import vtk
import qt
import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin

class TotalSpineSeg(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("TotalSpineSeg")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Segmentation")]
        self.parent.dependencies = []
        self.parent.contributors = ["Yehuda Warszawer (Sheba Medical Center), Nathan Molinier (Polytechnique Montreal), Anat Achiron, Julien Cohen-Adad"]
        self.parent.helpText = _("""
3D Slicer extension for fully automatic spine MRI and CT segmentation using TotalSpineSeg AI model.
See more information in the <a href="https://github.com/neuropoly/SlicerTotalSpineSeg">extension documentation</a>.
""")
        self.parent.acknowledgementText = _("""
This module uses <a href="https://github.com/neuropoly/totalspineseg">TotalSpineSeg</a>.
If you use the TotalSpineSeg function from this software in your research, please cite:
Warszawer Y, Molinier N, Valosek J, Shirbint E, Benveniste PL, Achiron A, Eshaghi A and Cohen-Adad J. 
Fully Automatic Vertebrae and Spinal Cord Segmentation Using a Hybrid Approach Combining nnU-Net and Iterative Algorithm. 
Proceedings of the 32th Annual Meeting of ISMRM. 2024
""")

class TotalSpineSegWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self.logic = None
        self._parameterNode = None
        self._updatingGUIFromParameterNode = False

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/TotalSpineSeg.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        uiWidget.setMRMLScene(slicer.mrmlScene)

        self.logic = TotalSpineSegLogic()
        self.logic.logCallback = self.addLog

        # Setup Icons
        # Use text for now as specific icons are not in the resource folder
        # eyeIcon = qt.QIcon(":/Icons/VisibleOn.png") 
        # threeDIcon = qt.QIcon(":/Icons/MakeModel.png")

        # Try to load standard icons from Slicer resources
        # Note: These paths are standard in Slicer but might vary.
        # If they fail, we fallback to text.
        self.eyeIcon = qt.QIcon(":/Icons/VisibleOn.png")
        self.eyeOffIcon = qt.QIcon(":/Icons/VisibleOff.png")
        threeDIcon = qt.QIcon(":/Icons/MakeModel.png")

        for btn in [self.ui.visibleStep2Button, self.ui.visibleStep1Button, self.ui.visibleLevelsButton, self.ui.visibleCordButton, self.ui.visibleCanalButton]:
            btn.setIcon(self.eyeIcon)
            if self.eyeIcon.isNull():
                btn.setText("👁")
            else:
                btn.setText("")
            btn.setToolTip(_("Show/Hide"))
            btn.setFixedSize(24, 24)

        for btn in [self.ui.show3DStep2Button, self.ui.show3DStep1Button, self.ui.show3DLevelsButton, self.ui.show3DCordButton, self.ui.show3DCanalButton]:
            btn.setIcon(threeDIcon)
            if threeDIcon.isNull():
                btn.setText("3D")
            else:
                btn.setText("")
            btn.setToolTip(_("Show/Hide 3D"))
            btn.setFixedSize(24, 24)

        # Setup Load Buttons
        for btn in [self.ui.loadStep2FileButton, self.ui.loadStep1FileButton, self.ui.loadLevelsFileButton, self.ui.loadCordFileButton, self.ui.loadCanalFileButton, self.ui.inputVolumeFileButton, self.ui.inputLocalizerFileButton]:
            btn.setIcon(qt.QIcon())
            btn.setText("...")
            btn.setToolTip(_("Load from file"))
            btn.setFixedSize(24, 24)

        # Fix Width Issues
        for combo in [self.ui.inputVolumeSelector, self.ui.inputLocalizerSelector, self.ui.outputStep1Selector, self.ui.outputStep2Selector, 
                      self.ui.outputCordSelector, self.ui.outputCanalSelector, self.ui.outputLevelsSelector,
                      self.ui.loadStep2Selector, self.ui.loadStep1Selector, self.ui.loadLevelsSelector, 
                      self.ui.loadCordSelector, self.ui.loadCanalSelector]:
            combo.setSizePolicy(qt.QSizePolicy.Ignored, qt.QSizePolicy.Fixed)
        
        # Ensure localizer selector is enabled and configured
        self.ui.inputLocalizerSelector.enabled = True
        self.ui.inputLocalizerSelector.noneEnabled = True
        self.ui.inputLocalizerSelector.addEnabled = False
        self.ui.inputLocalizerSelector.removeEnabled = False
        self.ui.inputLocalizerSelector.renameEnabled = False
        self.ui.inputLocalizerSelector.editEnabled = False
        self.ui.inputLocalizerSelector.setMRMLScene(slicer.mrmlScene)

        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.inputLocalizerSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.outputStep1Selector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.outputStep2Selector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.outputCordSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.outputCanalSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.outputLevelsSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        
        self.ui.cpuCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.applyTerminologyCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.isoCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)

        self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
        self.ui.packageInfoUpdateButton.connect('clicked(bool)', self.onPackageInfoUpdate)
        self.ui.packageUpgradeButton.connect('clicked(bool)', self.onPackageUpgrade)

        self.ui.loadStep2Selector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.loadStep1Selector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.loadLevelsSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.loadCordSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)
        self.ui.loadCanalSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

        # Apply styles when selected in Load tab
        self.ui.loadCordSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onLoadCordChanged)
        self.ui.loadCanalSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onLoadCanalChanged)

        self.ui.visibleStep2Button.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleStep2Button, self.ui.loadStep2Selector.currentNode()))
        self.ui.visibleStep1Button.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleStep1Button, self.ui.loadStep1Selector.currentNode()))
        self.ui.visibleLevelsButton.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleLevelsButton, self.ui.loadLevelsSelector.currentNode()))
        self.ui.visibleCordButton.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleCordButton, self.ui.loadCordSelector.currentNode()))
        self.ui.visibleCanalButton.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleCanalButton, self.ui.loadCanalSelector.currentNode()))

        self.ui.show3DStep2Button.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.loadStep2Selector.currentNode()))
        self.ui.show3DStep1Button.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.loadStep1Selector.currentNode()))
        self.ui.show3DLevelsButton.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.loadLevelsSelector.currentNode()))
        self.ui.show3DCordButton.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.loadCordSelector.currentNode()))
        self.ui.show3DCanalButton.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.loadCanalSelector.currentNode()))

        self.ui.loadStep2FileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.loadStep2Selector))
        self.ui.loadStep1FileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.loadStep1Selector))
        self.ui.loadLevelsFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.loadLevelsSelector))
        self.ui.loadCordFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.loadCordSelector))
        self.ui.loadCanalFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.loadCanalSelector))
        self.ui.inputVolumeFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.inputVolumeSelector))
        self.ui.inputLocalizerFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.inputLocalizerSelector))

        self.initializeParameterNode()
        self.onSelect()

    def cleanup(self):
        self.removeObservers()

    def enter(self):
        self.initializeParameterNode()

    def exit(self):
        if self._parameterNode:
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    def onSceneStartClose(self, caller, event):
        self.setParameterNode(None)
        # Explicitly clear selectors to prevent Subject Hierarchy warnings during close
        for selector in [self.ui.inputVolumeSelector, self.ui.inputLocalizerSelector, self.ui.outputStep1Selector, self.ui.outputStep2Selector, 
                         self.ui.outputCordSelector, self.ui.outputCanalSelector, self.ui.outputLevelsSelector,
                         self.ui.loadStep1Selector, self.ui.loadStep2Selector, self.ui.loadCordSelector, 
                         self.ui.loadCanalSelector, self.ui.loadLevelsSelector]:
            selector.setCurrentNode(None)

    def onSceneEndClose(self, caller, event):
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self):
        self.setParameterNode(self.logic.getParameterNode())
        if not self._parameterNode.GetNodeReference("InputVolume"):
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self._parameterNode.SetNodeReferenceID("InputVolume", firstVolumeNode.GetID())

    def setParameterNode(self, inputParameterNode):
        if inputParameterNode:
            self.logic.setDefaultParameters(inputParameterNode)
        if self._parameterNode is not None:
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
        self._parameterNode = inputParameterNode
        if self._parameterNode is not None:
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
        self.updateGUIFromParameterNode()

    def updateGUIFromParameterNode(self, caller=None, event=None):
        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return
        self._updatingGUIFromParameterNode = True

        self.ui.inputVolumeSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))
        self.ui.inputLocalizerSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputLocalizer"))
        self.ui.outputStep1Selector.setCurrentNode(self._parameterNode.GetNodeReference("OutputStep1"))
        self.ui.outputStep2Selector.setCurrentNode(self._parameterNode.GetNodeReference("OutputStep2"))
        self.ui.outputCordSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputCord"))
        self.ui.outputCanalSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputCanal"))
        self.ui.outputLevelsSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputLevels"))
        
        self.ui.cpuCheckBox.checked = self._parameterNode.GetParameter("CPU") == "true"
        self.ui.applyTerminologyCheckBox.checked = self._parameterNode.GetParameter("UseStandardSegmentNames") == "true"
        self.ui.isoCheckBox.checked = self._parameterNode.GetParameter("Iso") == "true"

        self.ui.loadStep1Selector.setCurrentNode(self._parameterNode.GetNodeReference("OutputStep1"))
        self.ui.loadStep2Selector.setCurrentNode(self._parameterNode.GetNodeReference("OutputStep2"))
        self.ui.loadCordSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputCord"))
        self.ui.loadCanalSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputCanal"))
        self.ui.loadLevelsSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputLevels"))

        self.onSelect()
        self._updatingGUIFromParameterNode = False

    def updateParameterNodeFromGUI(self, caller=None, event=None):
        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return
        
        wasModified = self._parameterNode.StartModify()
        
        self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputVolumeSelector.currentNodeID)
        self._parameterNode.SetNodeReferenceID("InputLocalizer", self.ui.inputLocalizerSelector.currentNodeID)
        self._parameterNode.SetNodeReferenceID("OutputStep1", self.ui.outputStep1Selector.currentNodeID)
        self._parameterNode.SetNodeReferenceID("OutputStep2", self.ui.outputStep2Selector.currentNodeID)
        self._parameterNode.SetNodeReferenceID("OutputCord", self.ui.outputCordSelector.currentNodeID)
        self._parameterNode.SetNodeReferenceID("OutputCanal", self.ui.outputCanalSelector.currentNodeID)
        self._parameterNode.SetNodeReferenceID("OutputLevels", self.ui.outputLevelsSelector.currentNodeID)
        
        self._parameterNode.SetParameter("CPU", "true" if self.ui.cpuCheckBox.checked else "false")
        self._parameterNode.SetParameter("UseStandardSegmentNames", "true" if self.ui.applyTerminologyCheckBox.checked else "false")
        self._parameterNode.SetParameter("Iso", "true" if self.ui.isoCheckBox.checked else "false")

        if caller == self.ui.loadStep1Selector:
             self._parameterNode.SetNodeReferenceID("OutputStep1", self.ui.loadStep1Selector.currentNodeID)
        if caller == self.ui.loadStep2Selector:
             self._parameterNode.SetNodeReferenceID("OutputStep2", self.ui.loadStep2Selector.currentNodeID)
        if caller == self.ui.loadCordSelector:
             self._parameterNode.SetNodeReferenceID("OutputCord", self.ui.loadCordSelector.currentNodeID)
        if caller == self.ui.loadCanalSelector:
             self._parameterNode.SetNodeReferenceID("OutputCanal", self.ui.loadCanalSelector.currentNodeID)
        if caller == self.ui.loadLevelsSelector:
             self._parameterNode.SetNodeReferenceID("OutputLevels", self.ui.loadLevelsSelector.currentNodeID)

        self._parameterNode.EndModify(wasModified)

    def onSelect(self):
        self.ui.applyButton.enabled = self.ui.inputVolumeSelector.currentNode() is not None

    def onLoadFile(self, selector):
        file_path = qt.QFileDialog.getOpenFileName(
            self.parent.parent(), 
            _("Load File"), 
            "", 
            _("Medical Images (*.nii.gz *.nii *.nrrd *.seg.nrrd);;All Files (*)")
        )
        if not file_path:
            return

        # Determine intended type based on selector
        isSegmentation = selector in [self.ui.loadStep1Selector, self.ui.loadStep2Selector, self.ui.loadLevelsSelector, self.ui.inputLocalizerSelector]
        isCord = selector == self.ui.loadCordSelector
        isCanal = selector == self.ui.loadCanalSelector
        
        if isSegmentation:
            # Load as labelmap, convert to segmentation
            labelNode = slicer.util.loadLabelVolume(file_path, {"show": False})
            if labelNode:
                segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
                segNode.SetName(os.path.splitext(os.path.basename(file_path))[0])
                slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelNode, segNode)
                slicer.mrmlScene.RemoveNode(labelNode)
                if self.ui.loadApplyTerminologyCheckBox.checked:
                    self.logic.applyTotalSpineSegTerminology(segNode)
                
                segNode.CreateDefaultDisplayNodes()
                slicer.app.processEvents()
                selector.setCurrentNodeID(segNode.GetID())
        elif isCord or isCanal:
            # Load as volume, hidden initially to avoid replacing background
            volNode = slicer.util.loadVolume(file_path, {"show": False})
            if volNode:
                selector.setCurrentNode(volNode)
                # Note: onLoadCordChanged/onLoadCanalChanged will trigger and apply style/foreground
        else:
            # Input volume or generic
            volNode = slicer.util.loadVolume(file_path)
            if volNode:
                selector.setCurrentNode(volNode)

    def onApplyButton(self):
        self.ui.statusLabel.plainText = ''
        
        if not self.ui.outputStep1Selector.currentNode():
            self.ui.outputStep1Selector.addNode()
        
        try:
            slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
            self.logic.setupPythonRequirements()
            slicer.app.restoreOverrideCursor()
        except Exception as e:
            slicer.app.restoreOverrideCursor()
            import traceback
            traceback.print_exc()
            self.ui.statusLabel.appendPlainText(_("Failed to install Python dependencies:\\n{exception}\\n").format(exception=e))
            return

        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            self.logic.process(
                inputVolume=self.ui.inputVolumeSelector.currentNode(),
                outputStep1=self.ui.outputStep1Selector.currentNode(),
                outputStep2=self.ui.outputStep2Selector.currentNode(),
                outputCord=self.ui.outputCordSelector.currentNode(),
                outputCanal=self.ui.outputCanalSelector.currentNode(),
                outputLevels=self.ui.outputLevelsSelector.currentNode(),
                cpu=self.ui.cpuCheckBox.checked,
                iso=self.ui.isoCheckBox.checked,
                useStandardNames=self.ui.applyTerminologyCheckBox.checked,
                inputLocalizer=self.ui.inputLocalizerSelector.currentNode()
            )
        
        self.ui.loadApplyTerminologyCheckBox.checked = self.ui.applyTerminologyCheckBox.checked
        self.ui.statusLabel.appendPlainText("\\n" + _("Processing finished."))
        self.ui.tabWidget.setCurrentIndex(1)

    def onLoadCordChanged(self, node):
        if node:
            self.applyVolumeStyle(node, "vtkMRMLColorTableNodeGreen")

    def onLoadCanalChanged(self, node):
        if node:
            self.applyVolumeStyle(node, "vtkMRMLColorTableNodeYellow")

    def applyVolumeStyle(self, node, colorNodeID):
        if node.IsA("vtkMRMLScalarVolumeNode"):
            if not node.GetImageData():
                return
            displayNode = node.GetDisplayNode()
            if not displayNode:
                node.CreateDefaultDisplayNodes()
                displayNode = node.GetDisplayNode()
            
            displayNode.SetApplyThreshold(True)
            displayNode.SetLowerThreshold(0.5)
            displayNode.SetAndObserveColorNodeID(colorNodeID)
            
            # Set as Foreground
            slicer.util.setSliceViewerLayers(foreground=node, foregroundOpacity=1.0)

    def onVisibilityToggled(self, button, node):
        if not node: return
        visible = True
        if node.IsA("vtkMRMLSegmentationNode"):
            displayNode = node.GetDisplayNode()
            if displayNode:
                visible = not displayNode.GetVisibility()
                displayNode.SetVisibility(visible)
        elif node.IsA("vtkMRMLScalarVolumeNode"):
            layoutManager = slicer.app.layoutManager()
            sliceLogic = layoutManager.sliceWidget("Red").sliceLogic()
            fg = sliceLogic.GetForegroundLayer().GetVolumeNode()
            if fg == node:
                slicer.util.setSliceViewerLayers(foreground=None)
                visible = False
            else:
                slicer.util.setSliceViewerLayers(foreground=node, foregroundOpacity=1.0)
                visible = True
        
        if visible:
            button.setIcon(self.eyeIcon)
            if self.eyeIcon.isNull(): button.setText("👁")
        else:
            button.setIcon(self.eyeOffIcon)
            if self.eyeOffIcon.isNull(): button.setText("○")

    def on3DToggled(self, node):
        if not node: return
        if node.IsA("vtkMRMLSegmentationNode"):
            displayNode = node.GetDisplayNode()
            if not displayNode:
                node.CreateDefaultDisplayNodes()
                displayNode = node.GetDisplayNode()
            if displayNode.GetPreferredDisplayRepresentationName3D() != 'Closed surface':
                 displayNode.SetPreferredDisplayRepresentationName3D('Closed surface')
            segmentation = node.GetSegmentation()
            if segmentation.GetNumberOfSegments() > 0:
                if not segmentation.ContainsRepresentation('Closed surface'):
                     node.CreateClosedSurfaceRepresentation()
                     displayNode.SetVisibility3D(True)
                else:
                     visible = displayNode.GetVisibility3D()
                     displayNode.SetVisibility3D(not visible)
        elif node.IsA("vtkMRMLScalarVolumeNode"):
            volRenLogic = slicer.modules.volumerendering.logic()
            displayNode = volRenLogic.GetFirstVolumeRenderingDisplayNode(node)
            if displayNode:
                displayNode.SetVisibility(not displayNode.GetVisibility())
            else:
                displayNode = volRenLogic.CreateDefaultVolumeRenderingNodes(node)
                displayNode.SetVisibility(True)

    def onPackageInfoUpdate(self):
        self.ui.packageInfoTextBrowser.plainText = ''
        with slicer.util.tryWithErrorDisplay(_("Failed to get TotalSpineSeg package version information"), waitCursor=True):
            self.ui.packageInfoTextBrowser.plainText = self.logic.installedTotalSpineSegPythonPackageInfo().rstrip()

    def onPackageUpgrade(self):
        with slicer.util.tryWithErrorDisplay(_("Failed to upgrade TotalSpineSeg"), waitCursor=True):
            self.logic.setupPythonRequirements(upgrade=True)
        self.onPackageInfoUpdate()
        if not slicer.util.confirmOkCancelDisplay(_("This TotalSpineSeg update requires a 3D Slicer restart. Press OK to restart.")):
            raise ValueError(_("Restart was cancelled."))
        else:
            slicer.util.restart()

    def addLog(self, text):
        self.ui.statusLabel.appendPlainText(text)
        slicer.app.processEvents()

class InstallError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message
    def __str__(self):
        return self.message

class TotalSpineSegLogic(ScriptedLoadableModuleLogic):
    def __init__(self):
        ScriptedLoadableModuleLogic.__init__(self)
        self.logCallback = None
        self.clearOutputFolder = True
        self.totalSpineSegPythonPackageDownloadUrl = "https://github.com/neuropoly/totalspineseg/archive/master.zip"

    def log(self, text):
        logging.info(text)
        if self.logCallback:
            self.logCallback(text)

    def setDefaultParameters(self, parameterNode):
        if not parameterNode.GetParameter("UseStandardSegmentNames"):
            parameterNode.SetParameter("UseStandardSegmentNames", "true")

    def installedTotalSpineSegPythonPackageDownloadUrl(self):
        import importlib.metadata
        import json
        try:
            metadataPath = [p for p in importlib.metadata.files('totalspineseg') if 'direct_url.json' in str(p)][0]
            with open(metadataPath.locate()) as json_file:
                data = json.load(json_file)
            return data['url']
        except:
            return None

    def installedTotalSpineSegPythonPackageInfo(self):
        import shutil
        import subprocess
        versionInfo = subprocess.check_output([shutil.which('PythonSlicer'), "-m", "pip", "show", "totalspineseg"]).decode()
        downloadUrl = self.installedTotalSpineSegPythonPackageDownloadUrl()
        if downloadUrl:
            versionInfo += "Download URL: " + downloadUrl
        return versionInfo

    def setupPythonRequirements(self, upgrade=False):
        import importlib.metadata
        import packaging
        try:
            import pandas
        except ModuleNotFoundError:
            slicer.util.pip_install("pandas")
        try:
            import dicom2nifti
        except ModuleNotFoundError:
            slicer.util.pip_install("dicom2nifti<=2.5.1")

        confirmPackagesToInstall = []
        try:
          import PyTorchUtils
        except ModuleNotFoundError:
          raise InstallError("This module requires PyTorch extension. Install it from the Extensions Manager.")

        minimumTorchVersion = "2.0.0"
        torchLogic = PyTorchUtils.PyTorchUtilsLogic()
        if not torchLogic.torchInstalled():
            confirmPackagesToInstall.append("PyTorch")

        try:
            import SlicerNNUNetLib
        except ModuleNotFoundError:
            raise InstallError("This module requires SlicerNNUNet extension. Install it from the Extensions Manager.")

        minimumNNUNetVersion = "2.2.1"
        nnunetlogic = SlicerNNUNetLib.InstallLogic(doAskConfirmation=False)
        nnunetlogic.getInstalledNNUnetVersion()
        from packaging.requirements import Requirement
        if not nnunetlogic.isPackageInstalled(Requirement("nnunetv2")):
            confirmPackagesToInstall.append("nnunetv2")

        if confirmPackagesToInstall:
            if not slicer.util.confirmOkCancelDisplay(
                _("This module requires installation of additional Python packages. Installation needs network connection and may take several minutes. Click OK to proceed."),
                _("Confirm Python package installation"),
                detailedText=_("Python packages that will be installed: {package_list}").format(package_list=', '.join(confirmPackagesToInstall))
                ):
                raise InstallError("User cancelled.")

        if "PyTorch" in confirmPackagesToInstall:
            self.log(_('PyTorch Python package is required. Installing... (it may take several minutes)'))
            torch = torchLogic.installTorch(askConfirmation=False, torchVersionRequirement = f">={minimumTorchVersion}")
            if torch is None:
                raise InstallError("This module requires PyTorch extension. Install it from the Extensions Manager.")
        else:
            from packaging import version
            if version.parse(torchLogic.torch.__version__) < version.parse(minimumTorchVersion):
                raise InstallError(f'PyTorch version {torchLogic.torch.__version__} is not compatible with this module.')

        if "nnunetv2" in confirmPackagesToInstall:
            self.log(_('nnunetv2 package is required. Installing... (it may take several minutes)'))
            nnunet = nnunetlogic.setupPythonRequirements(f"nnunetv2>={minimumNNUNetVersion}")
            if not nnunet:
                raise InstallError("This module requires SlicerNNUNet extension. Install it from the Extensions Manager.")
        else:
            installed_nnunet_version = nnunetlogic.getInstalledNNUnetVersion()
            if installed_nnunet_version < version.parse(minimumNNUNetVersion):
                raise InstallError(f'nnUNetv2 version {installed_nnunet_version} is not compatible with this module.')

        needToInstall = False
        try:
            import totalspineseg
        except ImportError:
            needToInstall = True

        if needToInstall or upgrade:
            self.log(_('TotalSpineSeg is required. Installing... (it may take several minutes)'))
            slicer.util.pip_install("totalspineseg[nnunetv2] --upgrade" if upgrade else "totalspineseg[nnunetv2]")
            self.log(_('TotalSpineSeg installation completed successfully.'))

    def logProcessOutput(self, proc):
        output = ""
        from subprocess import CalledProcessError
        while True:
            try:
                line = proc.stdout.readline()
                if not line:
                    break
                self.log(line.rstrip())
            except UnicodeDecodeError:
                pass
        proc.wait()
        if proc.returncode != 0:
            raise CalledProcessError(proc.returncode, proc.args, output=proc.stdout, stderr=proc.stderr)

    def process(self, inputVolume, outputStep1, outputStep2=None, outputCord=None, outputCanal=None, outputLevels=None, cpu=False, iso=False, useStandardNames=True, inputLocalizer=None):
        if not inputVolume:
            raise ValueError("Input volume is invalid")

        import time
        startTime = time.time()
        
        import shutil
        tempFolder = slicer.util.tempDirectory()
        inputFile = os.path.join(tempFolder, "input.nii")
        outputFolder = os.path.join(tempFolder, "output")
        os.makedirs(outputFolder, exist_ok=True)

        self.log(_("Writing input file to {input_file}").format(input_file=inputFile))
        slicer.util.saveNode(inputVolume, inputFile)

        pythonSlicerExecutablePath = shutil.which('PythonSlicer')
        if not pythonSlicerExecutablePath:
             raise RuntimeError("Python was not found")

        cmd = [pythonSlicerExecutablePath, "-m", "totalspineseg.inference", inputFile, outputFolder]
        
        if inputLocalizer:
            inputLocalizerFile = os.path.join(tempFolder, "localizer.nii.gz")
            self.log(_("Writing localizer file to {localizer_file}").format(localizer_file=inputLocalizerFile))
            
            # Export segmentation to labelmap with correct pixel values
            mapping = self.getTerminologyMapping()
            reverseMapping = {v: k for k, v in mapping.items()}
            
            segmentationNode = inputLocalizer
            segmentation = segmentationNode.GetSegmentation()
            
            # Create a temporary labelmap node
            labelmapNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
            
            # We need to manually construct the labelmap because ExportSegmentsToLabelmapNode 
            # doesn't easily allow specifying arbitrary pixel values for segments by name.
            # However, we can use a trick: create a temporary segmentation, rename segments to their IDs, 
            # and then export? No, Slicer generates IDs.
            
            # Better approach: Use the segment IDs if they match, or iterate and paint.
            # Most robust: Create a blank labelmap with same geometry, then iterate segments and add them.
            
            # 1. Initialize labelmap with correct geometry
            if inputVolume:
                labelmapNode.CopyOrientation(inputVolume)
                labelmapNode.SetOrigin(inputVolume.GetOrigin())
                labelmapNode.SetSpacing(inputVolume.GetSpacing())
                dims = inputVolume.GetImageData().GetDimensions()
                # We need to allocate the image data. 
                # Easier way: Export visible segments to labelmap, then remap values?
                # Or use Slicer's export with a color table?
                pass

            # Let's try the simplest approach first: 
            # If the segments are named "vertebrae_C1", we know the ID is 11.
            # We can create a color table node, set the names and values, and use that for export?
            # No, export uses the segment's binary representation.
            
            # Let's use `slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode`
            # It takes a list of segment IDs.
            
            # We will create a new temporary segmentation node.
            tempSegNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
            if segmentationNode.GetTransformNodeID():
                tempSegNode.SetAndObserveTransformNodeID(segmentationNode.GetTransformNodeID())
            
            # Copy segments to temp node, but ensure we track which segment maps to which value
            validSegments = []
            
            for i in range(segmentation.GetNumberOfSegments()):
                segId = segmentation.GetNthSegmentID(i)
                segment = segmentation.GetSegment(segId)
                name = segment.GetName()
                
                val = None
                if name in reverseMapping:
                    val = reverseMapping[name]
                else:
                    # Try to parse number
                    try:
                        val = int(name)
                    except:
                        pass
                
                if val is not None:
                    # Add to temp seg
                    newSegment = slicer.vtkSegment()
                    newSegment.DeepCopy(segment)
                    tempSegNode.GetSegmentation().AddSegment(newSegment)
                    newSegId = tempSegNode.GetSegmentation().GetSegmentIdBySegment(newSegment)
                    validSegments.append((newSegId, val))

            # Now export to labelmap. 
            # We need to ensure the pixel value matches 'val'.
            # We can do this by exporting each segment individually to a temporary labelmap with the specific value, 
            # and adding it to the main accumulator labelmap.
            
            # Create accumulator labelmap
            slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(tempSegNode, [], labelmapNode, inputVolume)
            # Clear it (set to 0)
            image = labelmapNode.GetImageData()
            if image:
                image.GetPointData().GetScalars().FillComponent(0, 0)
            else:
                # If export failed to create image data (e.g. no reference volume), try without reference
                slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(tempSegNode, [], labelmapNode)
                image = labelmapNode.GetImageData()
                if image:
                    image.GetPointData().GetScalars().FillComponent(0, 0)

            if image:
                import vtk.util.numpy_support as vtk_np
                import numpy as np
                
                # Get numpy array of accumulator
                acc_array = vtk_np.vtk_to_numpy(image.GetPointData().GetScalars())
                
                # Iterate segments
                for segId, val in validSegments:
                    # Export single segment to temp labelmap
                    tempLabel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
                    slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(tempSegNode, [segId], tempLabel, labelmapNode)
                    
                    temp_image = tempLabel.GetImageData()
                    if temp_image:
                        temp_array = vtk_np.vtk_to_numpy(temp_image.GetPointData().GetScalars())
                        # Where temp_array > 0, set acc_array to val
                        acc_array[temp_array > 0] = val
                    
                    slicer.mrmlScene.RemoveNode(tempLabel)
                
                image.Modified()
            
            # Save the labelmap
            slicer.util.saveNode(labelmapNode, inputLocalizerFile)
            
            # Cleanup
            slicer.mrmlScene.RemoveNode(labelmapNode)
            slicer.mrmlScene.RemoveNode(tempSegNode)
            
            cmd.extend(["--loc", inputLocalizerFile])

        if cpu:
            cmd.extend(["--device", "cpu"])
        if iso:
            cmd.append("--iso")
            
        if outputStep2 is None:
            cmd.append("--step1")
            
        keep_only = []
        if outputStep1:
            keep_only.append('step1_output')
        if outputStep2:
            keep_only.append('step2_output')
        if outputCord:
            keep_only.append('step1_cord')
        if outputCanal:
            keep_only.append('step1_canal')
        if outputLevels:
            keep_only.append('step1_levels')
            
        if keep_only:
            cmd.append("--keep-only")
            cmd.extend(keep_only)

        self.log(_('Running TotalSpineSeg AI...'))
        self.log(f"Command: {cmd}")

        proc = slicer.util.launchConsoleProcess(cmd)
        self.logProcessOutput(proc)

        self.log(_('Importing results...'))

        if outputStep1:
            self.importResult(outputStep1, os.path.join(outputFolder, "step1_output"), "TotalSpineSeg_Step1", applyTerm=useStandardNames, renameSacrum=True)

        if outputStep2:
            self.importResult(outputStep2, os.path.join(outputFolder, "step2_output"), "TotalSpineSeg_Step2", applyTerm=useStandardNames, renameSacrum=True)

        if outputCord:
            self.importResult(outputCord, os.path.join(outputFolder, "step1_cord"), "TotalSpineSeg_Cord", isSoft=True, colorNodeID="vtkMRMLColorTableNodeGreen")
            slicer.util.setSliceViewerLayers(foreground=outputCord, foregroundOpacity=1.0)

        if outputCanal:
            self.importResult(outputCanal, os.path.join(outputFolder, "step1_canal"), "TotalSpineSeg_Canal", isSoft=True, colorNodeID="vtkMRMLColorTableNodeYellow")
            slicer.util.setSliceViewerLayers(foreground=outputCanal, foregroundOpacity=1.0)

        if outputLevels:
            self.importResult(outputLevels, os.path.join(outputFolder, "step1_levels"), "TotalSpineSeg_Levels")

        if self.clearOutputFolder:
            shutil.rmtree(tempFolder)
            
        stopTime = time.time()
        self.log(_("Processing completed in {time:.2f}s").format(time=stopTime-startTime))

    def importResult(self, node, folder, prefix, isSoft=False, applyTerm=False, colorNodeID=None, renameSacrum=False):
        import glob
        if not os.path.exists(folder):
            self.log(f"Folder {folder} not found.")
            return
            
        files = glob.glob(os.path.join(folder, "*.nii.gz")) + glob.glob(os.path.join(folder, "*.nii"))
        if not files:
            return
            
        path = files[0]
        self.log(f"Importing {path} to {node.GetName()}")
        
        if isSoft:
            tempNode = slicer.util.loadVolume(path, {"show": False})
            if tempNode:
                node.SetAndObserveImageData(tempNode.GetImageData())
                node.CopyOrientation(tempNode)
                slicer.mrmlScene.RemoveNode(tempNode)
                
                displayNode = node.GetDisplayNode()
                if not displayNode:
                    node.CreateDefaultDisplayNodes()
                    displayNode = node.GetDisplayNode()
                
                displayNode.SetApplyThreshold(True)
                displayNode.SetLowerThreshold(0.5)
                if colorNodeID:
                    displayNode.SetAndObserveColorNodeID(colorNodeID)
        else:
            labelNode = slicer.util.loadLabelVolume(path, {"show": False})
            if labelNode:
                node.GetSegmentation().RemoveAllSegments()
                slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelNode, node)
                slicer.mrmlScene.RemoveNode(labelNode)
                
                if not node.GetDisplayNode():
                    node.CreateDefaultDisplayNodes()
                
                if applyTerm:
                    self.applyTotalSpineSegTerminology(node)
                
                if renameSacrum:
                    seg = node.GetSegmentation()
                    for i in range(seg.GetNumberOfSegments()):
                        sid = seg.GetNthSegmentID(i)
                        s = seg.GetSegment(sid)
                        if s.GetName() == "50" or s.GetName() == "sacrum":
                            s.SetName("Vertebrae")

    def getTerminologyMapping(self):
        return {
            1: "spinal_cord", 2: "spinal_canal", 3: "vertebrae_L5", 
            11: "vertebrae_C1", 12: "vertebrae_C2", 13: "vertebrae_C3", 14: "vertebrae_C4", 15: "vertebrae_C5", 16: "vertebrae_C6", 17: "vertebrae_C7",
            21: "vertebrae_T1", 22: "vertebrae_T2", 23: "vertebrae_T3", 24: "vertebrae_T4", 25: "vertebrae_T5", 26: "vertebrae_T6", 27: "vertebrae_T7", 28: "vertebrae_T8", 29: "vertebrae_T9", 30: "vertebrae_T10", 31: "vertebrae_T11", 32: "vertebrae_T12",
            41: "vertebrae_L1", 42: "vertebrae_L2", 43: "vertebrae_L3", 44: "vertebrae_L4", 45: "vertebrae_L5", 46: "vertebrae_L6",
            50: "sacrum",
            63: "disc_C2_C3", 64: "disc_C3_C4", 65: "disc_C4_C5", 66: "disc_C5_C6", 67: "disc_C6_C7", 70: "disc_C7_T1", 
            71: "disc_T1_T2", 72: "disc_T2_T3", 73: "disc_T3_T4", 74: "disc_T4_T5", 75: "disc_T5_T6", 76: "disc_T6_T7", 77: "disc_T7_T8", 78: "disc_T8_T9", 79: "disc_T9_T10", 80: "disc_T10_T11", 81: "disc_T11_T12",
            91: "disc_T12_L1", 92: "disc_L1_L2", 93: "disc_L2_L3", 94: "disc_L3_L4", 95: "disc_L4_L5", 100: "disc_L5_S1"
        }

    def applyTotalSpineSegTerminology(self, node):
        segmentation = node.GetSegmentation()
        mapping = self.getTerminologyMapping()
        
        for i in range(segmentation.GetNumberOfSegments()):
            segmentId = segmentation.GetNthSegmentID(i)
            segment = segmentation.GetSegment(segmentId)
            segmentName = segment.GetName()
            labelValue = None
            try:
                labelValue = int(segmentName)
            except ValueError:
                import re
                numbers = re.findall(r'\d+', segmentName)
                if numbers:
                    labelValue = int(numbers[-1])
            
            if labelValue is not None and labelValue in mapping:
                segment.SetName(mapping[labelValue])

    def revertTotalSpineSegTerminology(self, node):
        segmentation = node.GetSegmentation()
        mapping = self.getTerminologyMapping()
        # Create reverse mapping: name -> id
        reverseMapping = {v: k for k, v in mapping.items()}
        
        for i in range(segmentation.GetNumberOfSegments()):
            segmentId = segmentation.GetNthSegmentID(i)
            segment = segmentation.GetSegment(segmentId)
            segmentName = segment.GetName()
            
            if segmentName in reverseMapping:
                # We set the name to the ID, but we also need to ensure the label value is correct if we were exporting to labelmap
                # However, Slicer's export to labelmap uses the segment ID or layer, not the name directly unless configured.
                # But wait, the CLI tool likely expects a labelmap where pixel values correspond to these IDs.
                # Slicer's ExportSegmentsToLabelmapNode uses the segment's label value if set, or generates new ones.
                # We need to ensure the segment's label value matches the ID.
                # But `segment` object doesn't have a label value property directly exposed easily for export control in all versions.
                # Actually, when exporting to labelmap, we can specify a color table or use the segment indices.
                
                # The easiest way to ensure the output labelmap has the correct values is to rename the segments to the string of the ID,
                # and then when exporting, Slicer might not automatically use that as the pixel value.
                
                # Better approach:
                # When we export the segmentation to a labelmap node for saving, we can control the label values.
                # Or, we can rename the segments to "1", "2", etc. and hope the export respects that? No.
                
                # Let's look at how we save the node. `slicer.util.saveNode(inputLocalizer, inputLocalizerFile)`
                # If it's a segmentation node, Slicer saves it as .seg.nrrd or .nrrd.
                # If we save as .nii.gz, Slicer exports it to a labelmap first.
                # We need to ensure that the exported labelmap has the correct pixel values.
                
                # To do this reliably:
                # 1. Create a temporary labelmap node.
                # 2. Export segments to this labelmap node, mapping specific segments to specific values.
                pass


class TotalSpineSegTest(ScriptedLoadableModuleTest):
    def setUp(self):
        slicer.mrmlScene.Clear()

    def runTest(self):
        self.setUp()
        self.test_TotalSpineSeg1()

    def test_TotalSpineSeg1(self):
        self.delayDisplay("Starting the test")
        import SampleData
        inputVolume = SampleData.downloadSample('MRHead')
        self.delayDisplay('Loaded test data set')
        outputStep1 = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')
        
        testLogic = False
        if testLogic:
            logic = TotalSpineSegLogic()
            logic.setupPythonRequirements()
            logic.process(inputVolume, outputStep1)
        else:
            logging.warning("test_TotalSpineSeg1 logic testing was skipped.")
        self.delayDisplay('Test passed')
