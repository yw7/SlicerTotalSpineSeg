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
Warszawer, Y., Molinier, N., Valosek, J., Benveniste, P. L., Bédard, S., Shirbint, E., ... & Cohen-Adad, J. (2025). 
TotalSpineSeg: Robust Spine Segmentation with Landmark-Based Labeling in MRI. ResearchGate preprint.
""")

class TotalSpineSegWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    def __init__(self, parent=None):
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)
        self.logic = None
        self._parameterNode = None
        self._updatingGUIFromParameterNode = False
        
        self.installAnimationTimer = qt.QTimer()
        self.installAnimationTimer.setInterval(500)
        self.installAnimationTimer.connect('timeout()', self.onInstallAnimationTimer)
        self.installAnimationCounter = 0

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/TotalSpineSeg.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create Install Widget (initially hidden)
        self.installWidget = qt.QWidget()
        self.installLayout = qt.QVBoxLayout(self.installWidget)
        
        self.installLabel = qt.QLabel("Some required Python packages are missing.")
        self.installLabel.setAlignment(qt.Qt.AlignCenter)
        self.installLayout.addWidget(self.installLabel)
        
        self.installButton = qt.QPushButton("Install Dependencies")
        self.installButton.connect('clicked(bool)', self.onInstallButton)
        self.installLayout.addWidget(self.installButton)
        
        self.installStatusLabel = qt.QLabel("")
        self.installStatusLabel.setAlignment(qt.Qt.AlignCenter)
        self.installLayout.addWidget(self.installStatusLabel)
        
        # Insert installWidget into the main UI layout before the statusLabel (output box)
        # This ensures it appears above the output box but below the tab widget (which is hidden when installing)
        uiLayout = uiWidget.layout()
        statusLabelIndex = uiLayout.indexOf(self.ui.statusLabel)
        if statusLabelIndex != -1:
            uiLayout.insertWidget(statusLabelIndex, self.installWidget)
        else:
            # Fallback if statusLabel not found in layout
            self.layout.addWidget(self.installWidget)
            
        self.installWidget.hide()

        self.logic = TotalSpineSegLogic()
        self.logic.logCallback = self.addLog
        self.logic.processingFinishedCallback = self.onProcessingFinished

        # Setup Icons
        # Try to load standard icons from Slicer resources. If they fail, fallback to text.
        self.eyeIcon = qt.QIcon(":/Icons/VisibleOn.png")
        self.eyeOffIcon = qt.QIcon(":/Icons/VisibleOff.png")
        threeDIcon = qt.QIcon(":/Icons/MakeModel.png")

        for btn in [self.ui.visibleInputButton, self.ui.visibleStep2Button, self.ui.visibleStep1Button, self.ui.visibleLevelsButton, self.ui.visibleCordButton, self.ui.visibleCanalButton]:
            btn.setIcon(self.eyeIcon)
            if self.eyeIcon.isNull():
                btn.setText("👁")
            else:
                btn.setText("")
            btn.setToolTip(_("Show/Hide"))
            btn.setFixedSize(24, 24)

        for btn in [self.ui.show3DInputButton, self.ui.show3DStep2Button, self.ui.show3DStep1Button, self.ui.show3DLevelsButton, self.ui.show3DCordButton, self.ui.show3DCanalButton]:
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
                      self.ui.outputCordSelector, self.ui.outputCanalSelector, self.ui.outputLevelsSelector]:
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

        # Apply styles when selected
        self.ui.outputCordSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onLoadCordChanged)
        self.ui.outputCanalSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onLoadCanalChanged)

        self.ui.visibleInputButton.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleInputButton, self.ui.inputVolumeSelector.currentNode()))
        self.ui.visibleStep2Button.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleStep2Button, self.ui.outputStep2Selector.currentNode()))
        self.ui.visibleStep1Button.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleStep1Button, self.ui.outputStep1Selector.currentNode()))
        self.ui.visibleLevelsButton.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleLevelsButton, self.ui.outputLevelsSelector.currentNode()))
        self.ui.visibleCordButton.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleCordButton, self.ui.outputCordSelector.currentNode()))
        self.ui.visibleCanalButton.connect('clicked(bool)', lambda b: self.onVisibilityToggled(self.ui.visibleCanalButton, self.ui.outputCanalSelector.currentNode()))

        self.ui.show3DInputButton.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.inputVolumeSelector.currentNode()))
        self.ui.show3DStep2Button.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.outputStep2Selector.currentNode()))
        self.ui.show3DStep1Button.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.outputStep1Selector.currentNode()))
        self.ui.show3DLevelsButton.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.outputLevelsSelector.currentNode()))
        self.ui.show3DCordButton.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.outputCordSelector.currentNode()))
        self.ui.show3DCanalButton.connect('clicked(bool)', lambda b: self.on3DToggled(self.ui.outputCanalSelector.currentNode()))

        self.ui.inputVolumeFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.inputVolumeSelector))
        self.ui.inputLocalizerFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.inputLocalizerSelector))
        
        # The new file buttons in outputs section
        self.ui.loadStep2FileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.outputStep2Selector))
        self.ui.loadStep1FileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.outputStep1Selector))
        self.ui.loadLevelsFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.outputLevelsSelector))
        self.ui.loadCordFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.outputCordSelector))
        self.ui.loadCanalFileButton.connect('clicked(bool)', lambda b: self.onLoadFile(self.ui.outputCanalSelector))

        self.initializeParameterNode()
        self.onSelect()

        # Check dependencies immediately if the module is already entered (e.g. on reload)
        if self.parent.isEntered:
            self.checkDependenciesAndToggleUI()

    def cleanup(self):
        self.removeObservers()
        self.installAnimationTimer.stop()

    def enter(self):
        self.initializeParameterNode()
        self.checkDependenciesAndToggleUI()

    def checkDependenciesAndToggleUI(self):
        try:
            slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
            missingPackages = self.logic.checkDependencies()
            slicer.app.restoreOverrideCursor()
        except Exception as e:
            slicer.app.restoreOverrideCursor()
            import traceback
            traceback.print_exc()
            missingPackages = [] # Assume installed or handle error? 
            # If check fails, better to show error.
            self.installLabel.setText(f"Error checking dependencies:\n{str(e)}")
            if hasattr(self.ui, 'inputsCollapsibleButton'):
                 self.ui.inputsCollapsibleButton.hide()
            self.installWidget.show()
            return

        if missingPackages:
            if hasattr(self.ui, 'inputsCollapsibleButton'):
                 self.ui.inputsCollapsibleButton.hide()
            self.installWidget.show()
            self.installLabel.setText(f"The following packages are missing:\n{', '.join(missingPackages)}\n\nPlease install them to use this module.")
            self.installButton.show()
        else:
            self.installWidget.hide()
            if hasattr(self.ui, 'inputsCollapsibleButton'):
                 self.ui.inputsCollapsibleButton.show()

    def onInstallButton(self):
        missingPackages = self.logic.checkDependencies()
        if not missingPackages:
            self.checkDependenciesAndToggleUI()
            return

        # No confirmation needed here as user explicitly clicked "Install Dependencies"

        self.installButton.enabled = False
        self.installStatusLabel.setText("Installing packages")
        self.installAnimationCounter = 0
        self.installAnimationTimer.start()
        slicer.app.processEvents()
        
        try:
            restartNeeded = self.logic.installPackages(missingPackages)
            self.installAnimationTimer.stop()
            self.installStatusLabel.setText("Installation complete.")
            
            if restartNeeded:
                if slicer.util.confirmOkCancelDisplay("Extensions installed. Slicer needs to be restarted. Restart now?"):
                    slicer.util.restart()
                return 
            
            # If no restart needed, re-check and show UI
            import importlib
            importlib.invalidate_caches()
            
            # Double check if packages are still missing
            stillMissing = self.logic.checkDependencies()
            if stillMissing:
                # If still missing after install, force restart
                if slicer.util.confirmOkCancelDisplay(f"Installation completed, but the following packages are not yet loaded: {', '.join(stillMissing)}.\n\nA restart is required to complete the setup. Restart now?"):
                    slicer.util.restart()
                else:
                    self.checkDependenciesAndToggleUI() # Will show missing list again
            else:
                self.checkDependenciesAndToggleUI()
            
            self.installButton.enabled = True
            
        except Exception as e:
            self.installAnimationTimer.stop()
            self.installStatusLabel.setText(f"Installation failed: {str(e)}")
            self.installButton.enabled = True
            import traceback
            traceback.print_exc()

    def exit(self):
        if self._parameterNode:
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    def onSceneStartClose(self, caller, event):
        self.setParameterNode(None)
        # Explicitly clear selectors to prevent Subject Hierarchy warnings during close
        for selector in [self.ui.inputVolumeSelector, self.ui.inputLocalizerSelector, self.ui.outputStep1Selector, self.ui.outputStep2Selector, 
                         self.ui.outputCordSelector, self.ui.outputCanalSelector, self.ui.outputLevelsSelector]:
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
        isSegmentation = selector in [self.ui.outputStep1Selector, self.ui.outputStep2Selector, self.ui.outputLevelsSelector, self.ui.inputLocalizerSelector]
        isCord = selector == self.ui.outputCordSelector
        isCanal = selector == self.ui.outputCanalSelector
        
        if isSegmentation:
            # Load as labelmap, convert to segmentation
            labelNode = slicer.util.loadLabelVolume(file_path, {"show": False})
            if labelNode:
                segNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
                segNode.SetName(os.path.splitext(os.path.basename(file_path))[0])
                slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelNode, segNode)
                slicer.mrmlScene.RemoveNode(labelNode)
                if self.ui.applyTerminologyCheckBox.checked:
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
        elif selector == self.ui.inputVolumeSelector:
             # Load as background
            volNode = slicer.util.loadVolume(file_path, {"show": True})
            if volNode:
                selector.setCurrentNode(volNode)
        else:
            # Generic
            volNode = slicer.util.loadVolume(file_path)
            if volNode:
                selector.setCurrentNode(volNode)

    def onInstallAnimationTimer(self):
        self.installAnimationCounter = (self.installAnimationCounter + 1) % 4
        dots = "." * self.installAnimationCounter
        text = f"Installing packages{dots}"
        if self.installWidget.isVisible():
            self.installStatusLabel.setText(text)
        else:
            self.ui.statusLabel.plainText = text

    def onApplyButton(self):
        self.ui.statusLabel.plainText = ''
        
        if not self.ui.outputStep1Selector.currentNode():
            self.ui.outputStep1Selector.addNode()
        
        # Check dependencies (failsafe)
        try:
            slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
            missingPackages = self.logic.checkDependencies()
            slicer.app.restoreOverrideCursor()
        except Exception as e:
            slicer.app.restoreOverrideCursor()
            import traceback
            traceback.print_exc()
            self.ui.statusLabel.plainText = f"Failed to check dependencies:\n{str(e)}"
            return

        if missingPackages:
            # Filter out extensions from the confirmation list as they handle their own confirmation/installation flow
            # or are assumed to be confirmed by the user's intent to use the module.
            # Only ask confirmation for Python packages that might be unexpected.
            displayPackages = [p for p in missingPackages if p not in ["PyTorch", "NNUNet"]]
            
            if displayPackages:
                if not slicer.util.confirmOkCancelDisplay(f"The following packages are missing and will be installed:\n{', '.join(displayPackages)}\n\nClick OK to install."):
                    self.ui.statusLabel.plainText = "Installation cancelled by user."
                    return

            self.ui.statusLabel.plainText = "Installing packages"
            self.installAnimationCounter = 0
            self.installAnimationTimer.start()
            slicer.app.processEvents()
            
            try:
                restartNeeded = self.logic.installPackages(missingPackages)
                self.installAnimationTimer.stop()
                self.ui.statusLabel.plainText = "Installation complete."
                
                if restartNeeded:
                    if slicer.util.confirmOkCancelDisplay("Extensions installed. Slicer needs to be restarted. Restart now?"):
                        slicer.util.restart()
                    return # Stop here
            except Exception as e:
                self.installAnimationTimer.stop()
                self.ui.statusLabel.plainText = f"Installation failed: {str(e)}"
                import traceback
                traceback.print_exc()
                return

        self.ui.applyButton.enabled = False
        self.ui.statusLabel.plainText = "Processing started..."
        slicer.app.processEvents()
        
        try:
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
                inputLocalizer=self.ui.inputLocalizerSelector.currentNode(),
                waitForCompletion=False
            )
        except Exception as e:
            self.ui.applyButton.enabled = True
            self.ui.statusLabel.plainText = f"Processing failed: {str(e)}"
            import traceback
            traceback.print_exc()

    def onProcessingFinished(self, success):
        self.ui.applyButton.enabled = True
        if success:
            self.ui.statusLabel.appendPlainText("\\n" + _("Processing finished."))
        else:
            self.ui.statusLabel.appendPlainText("\\n" + _("Processing failed."))

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
            
            if button == self.ui.visibleInputButton:
                bg = sliceLogic.GetBackgroundLayer().GetVolumeNode()
                if bg == node:
                    slicer.util.setSliceViewerLayers(background=None)
                    visible = False
                else:
                    slicer.util.setSliceViewerLayers(background=node)
                    visible = True
            else:
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
            self.logic.installPackages(["totalspineseg"])
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
        self.totalSpineSegPythonPackageDownloadUrl = "https://github.com/neuropoly/totalspineseg/archive/refs/tags/r20251124.zip"
        self.processRunner = None
        self.processingFinishedCallback = None

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

    def checkDependencies(self):
        import importlib
        importlib.invalidate_caches()
        from packaging.requirements import Requirement

        missingPackages = []
        em = slicer.app.extensionsManagerModel()

        # 1. Extensions
        # PyTorch
        if not em.isExtensionInstalled("PyTorch"):
            missingPackages.append("PyTorch")
        else:
            try:
                import PyTorchUtils
                torchLogic = PyTorchUtils.PyTorchUtilsLogic()
                if not torchLogic.torchInstalled():
                    missingPackages.append("PyTorch")
            except ImportError:
                missingPackages.append("PyTorch")

        # NNUNet
        if not em.isExtensionInstalled("NNUNet"):
            missingPackages.append("NNUNet")
        else:
            try:
                import SlicerNNUNetLib
                nnunetlogic = SlicerNNUNetLib.InstallLogic(doAskConfirmation=False)
                if not nnunetlogic.isPackageInstalled(Requirement("nnunetv2")):
                    missingPackages.append("nnunetv2")
            except ImportError:
                missingPackages.append("NNUNet")

        # 2. Python packages
        try:
            import pandas
        except ImportError:
            missingPackages.append("pandas")
        
        try:
            import dicom2nifti
        except ImportError:
            missingPackages.append("dicom2nifti")

        try:
            import totalspineseg
        except ImportError:
            missingPackages.append("totalspineseg")

        return list(set(missingPackages))

    def installPackages(self, packages):
        import importlib
        em = slicer.app.extensionsManagerModel()
        
        restartNeeded = False

        # Extensions
        if "PyTorch" in packages:
            if not em.isExtensionInstalled("PyTorch"):
                em.installExtensionFromServer("PyTorch")
                restartNeeded = True
            else:
                # Extension installed but checkDependencies failed (likely import error)
                # Try to install torch libs if possible, otherwise assume restart needed
                try:
                    import PyTorchUtils
                    torchLogic = PyTorchUtils.PyTorchUtilsLogic()
                    if not torchLogic.torchInstalled():
                        torchLogic.installTorch(askConfirmation=False)
                except ImportError:
                    # Extension installed but cannot import -> Restart needed
                    restartNeeded = True

        if "NNUNet" in packages:
            if not em.isExtensionInstalled("NNUNet"):
                em.installExtensionFromServer("NNUNet")
                restartNeeded = True
            else:
                 try:
                    import SlicerNNUNetLib
                 except ImportError:
                    restartNeeded = True
        
        if restartNeeded:
            return True

        # Python packages
        if "pandas" in packages:
            slicer.util.pip_install("pandas")
        if "dicom2nifti" in packages:
            # Use specific version known to work with Slicer if needed, or just standard
            slicer.util.pip_install("dicom2nifti<=2.5.1")
        
        # PyTorch logic handled above, but if we are here, restart was not deemed needed yet.
        # If PyTorch was in packages, we might have installed torch libs.
        
        if "nnunetv2" in packages:
            slicer.util.pip_install("nnunetv2")

        if "totalspineseg" in packages:
            slicer.util.pip_install(self.totalSpineSegPythonPackageDownloadUrl)

        return False

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

    def process(self, inputVolume, outputStep1, outputStep2=None, outputCord=None, outputCanal=None, outputLevels=None, cpu=False, iso=False, useStandardNames=True, inputLocalizer=None, waitForCompletion=False):
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
            
            mapping = self.getTerminologyMapping()
            reverseMapping = {v: k for k, v in mapping.items()}
            
            segmentationNode = inputLocalizer
            segmentation = segmentationNode.GetSegmentation()
            
            labelmapNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
            if inputVolume:
                labelmapNode.CopyOrientation(inputVolume)
                labelmapNode.SetOrigin(inputVolume.GetOrigin())
                labelmapNode.SetSpacing(inputVolume.GetSpacing())
            
            tempSegNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
            if segmentationNode.GetTransformNodeID():
                tempSegNode.SetAndObserveTransformNodeID(segmentationNode.GetTransformNodeID())
            
            validSegments = []
            for i in range(segmentation.GetNumberOfSegments()):
                segId = segmentation.GetNthSegmentID(i)
                segment = segmentation.GetSegment(segId)
                name = segment.GetName()
                
                val = None
                if name in reverseMapping:
                    val = reverseMapping[name]
                else:
                    try:
                        val = int(name)
                    except ValueError:
                        pass
                
                if val is not None:
                    newSegment = slicer.vtkSegment()
                    newSegment.DeepCopy(segment)
                    tempSegNode.GetSegmentation().AddSegment(newSegment)
                    newSegId = tempSegNode.GetSegmentation().GetSegmentIdBySegment(newSegment)
                    validSegments.append((newSegId, val))

            slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(tempSegNode, [], labelmapNode, inputVolume)
            image = labelmapNode.GetImageData()
            
            if not image:
                slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(tempSegNode, [], labelmapNode)
                image = labelmapNode.GetImageData()

            if image:
                image.GetPointData().GetScalars().FillComponent(0, 0)
                import vtk.util.numpy_support as vtk_np
                
                acc_array = vtk_np.vtk_to_numpy(image.GetPointData().GetScalars())
                
                for segId, val in validSegments:
                    tempLabel = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode")
                    slicer.modules.segmentations.logic().ExportSegmentsToLabelmapNode(tempSegNode, [segId], tempLabel, labelmapNode)
                    
                    temp_image = tempLabel.GetImageData()
                    if temp_image:
                        temp_array = vtk_np.vtk_to_numpy(temp_image.GetPointData().GetScalars())
                        acc_array[temp_array > 0] = val
                    
                    slicer.mrmlScene.RemoveNode(tempLabel)
                
                image.Modified()
            
            slicer.util.saveNode(labelmapNode, inputLocalizerFile)
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

        if waitForCompletion:
            proc = slicer.util.launchConsoleProcess(cmd)
            self.logProcessOutput(proc)
            self.onProcessFinished(0, outputStep1, outputStep2, outputCord, outputCanal, outputLevels, useStandardNames, tempFolder, startTime, outputFolder)
        else:
            self.processRunner = qt.QProcess()
            env = qt.QProcessEnvironment.systemEnvironment()
            startupEnv = slicer.util.startupEnvironment()
            for key, value in startupEnv.items():
                env.insert(key, value)
            self.processRunner.setProcessEnvironment(env)
            
            self.processRunner.connect('readyReadStandardOutput()', self.onProcessOutput)
            self.processRunner.connect('readyReadStandardError()', self.onProcessOutput)
            self.processRunner.connect('finished(int, QProcess::ExitStatus)', lambda exitCode, exitStatus: self.onProcessFinished(
                exitCode, outputStep1, outputStep2, outputCord, outputCanal, outputLevels, useStandardNames, tempFolder, startTime, outputFolder))
            
            self.processRunner.start(cmd[0], cmd[1:])

    def onProcessOutput(self):
        if not self.processRunner:
            return
        self.processRunner.setReadChannel(qt.QProcess.StandardOutput)
        while self.processRunner.canReadLine():
            self.log(self.processRunner.readLine().data().decode('utf-8').rstrip())
        self.processRunner.setReadChannel(qt.QProcess.StandardError)
        while self.processRunner.canReadLine():
            self.log(self.processRunner.readLine().data().decode('utf-8').rstrip())

    def onProcessFinished(self, exitCode, outputStep1, outputStep2, outputCord, outputCanal, outputLevels, useStandardNames, tempFolder, startTime, outputFolder):
        import time
        if exitCode != 0:
            self.log("Process failed with exit code " + str(exitCode))
            if self.processingFinishedCallback:
                self.processingFinishedCallback(False)
            return

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
            import shutil
            shutil.rmtree(tempFolder)
            
        stopTime = time.time()
        self.log(_("Processing completed in {time:.2f}s").format(time=stopTime-startTime))
        
        if self.processingFinishedCallback:
            self.processingFinishedCallback(True)

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
            logic.process(inputVolume, outputStep1, waitForCompletion=True)
        else:
            logging.warning("test_TotalSpineSeg1 logic testing was skipped.")
        self.delayDisplay('Test passed')
