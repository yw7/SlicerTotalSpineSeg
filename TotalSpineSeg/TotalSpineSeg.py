import logging
import os
import re

import vtk

import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin


#
# TotalSpineSeg
#
#

class TotalSpineSeg(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("TotalSpineSeg")
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Segmentation")]
        self.parent.dependencies = []
        self.parent.contributors = ["Yehuda Warszawer (Sheba Medical Center), Nathan Molinier (Polytechnique Montreal), Anat Achiron, Julien Cohen-Adad"]
        self.parent.helpText = _("""
3D Slicer extension for fully automatic whole body CT segmentation using TotalSpineSeg AI model.
See more information in the <a href="https://github.com/neuropoly/SlicerTotalSpineSeg">extension documentation</a>.
""")
        self.parent.acknowledgementText = _("""
This module uses <a href="https://github.com/neuropoly/totalspineseg">TotalSpineSeg</a>.
If you use the TotalSpineSeg function from this software in your research, please cite:
Warszawer Y, Molinier N, Valosek J, Shirbint E, Benveniste PL, Achiron A, Eshaghi A and Cohen-Adad J. 
Fully Automatic Vertebrae and Spinal Cord Segmentation Using a Hybrid Approach Combining nnU-Net and Iterative Algorithm. 
Proceedings of the 32th Annual Meeting of ISMRM. 2024

Please also cite nnU-Net since it is used as the backbone:
Isensee, F., Jaeger, P. F., Kohl, S. A., Petersen, J., & Maier-Hein, K. H. (2021). 
nnU-Net: a self-configuring method for deep learning-based biomedical image segmentation. Nature methods, 18(2), 203-211.
""")
        slicer.app.connect("startupCompleted()", self.configureDefaultTerminology)

    def configureDefaultTerminology(self):
        moduleDir = os.path.dirname(self.parent.path)
        totalSpineSegTerminologyFilePath = os.path.join(moduleDir, 'Resources', 'SegmentationCategoryTypeModifier-TotalSpineSeg.term.json')
        tlogic = slicer.modules.terminologies.logic()
        self.terminologyName = tlogic.LoadTerminologyFromFile(totalSpineSegTerminologyFilePath)

#
# TotalSpineSegWidget
#

class TotalSpineSegWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._updatingGUIFromParameterNode = False

    def setup(self):
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/TotalSpineSeg.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = TotalSpineSegLogic()
        self.logic.logCallback = self.addLog

        for task in self.logic.tasks:
            taskTitle = self.logic.tasks[task]['title']
            taskTitle = self.logic.tasks[task]['title']
            self.ui.taskComboBox.addItem(taskTitle, task)

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # These connections ensure that whenever user changes some settings on the GUI, that is saved in the MRML scene
        # (in the selected parameter node).
        self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)

        self.ui.cpuCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.useStandardSegmentNamesCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.isoCheckBox.connect('toggled(bool)', self.updateParameterNodeFromGUI)
        self.ui.localizerVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.updateParameterNodeFromGUI)


        self.ui.taskComboBox.currentTextChanged.connect(self.updateParameterNodeFromGUI)
        self.ui.outputSegmentationSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.outputCordSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.outputCanalSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.outputLevelsSelector.setMRMLScene(slicer.mrmlScene)
        self.ui.localizerVolumeSelector.setMRMLScene(slicer.mrmlScene)

        # Connect observers to scene events
        self.ui.inputVolumeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
        self.ui.outputSegmentationSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
        self.ui.outputCordSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
        self.ui.outputCanalSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)
        self.ui.outputLevelsSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onSelect)


        self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)

        self.ui.packageInfoUpdateButton.connect('clicked(bool)', self.onPackageInfoUpdate)
        self.ui.packageUpgradeButton.connect('clicked(bool)', self.onPackageUpgrade)
        # self.ui.setLicenseButton.connect('clicked(bool)', self.onSetLicense) # License removed

        # Refresh Apply button state
        self.onSelect()

    def cleanup(self):
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.removeObservers()

    def enter(self):
        """
        Called each time the user opens this module.
        """
        # Make sure parameter node exists and observed
        self.initializeParameterNode()

    def exit(self):
        """
        Called each time the user opens a different module.
        """
        # Do not react to parameter node changes (GUI wlil be updated when the user enters into the module)
        if self._parameterNode:
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

    def onSceneStartClose(self, caller, event):
        """
        Called just before the scene is closed.
        """
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event):
        """
        Called just after the scene is closed.
        """
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
          self.initializeParameterNode()

    def initializeParameterNode(self):
        """
        Ensure parameter node exists and observed.
        """
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.GetNodeReference("InputVolume"):
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self._parameterNode.SetNodeReferenceID("InputVolume", firstVolumeNode.GetID())

    def setParameterNode(self, inputParameterNode):
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if inputParameterNode:
            self.logic.setDefaultParameters(inputParameterNode)

        # Unobserve previously selected parameter node and add an observer to the newly selected.
        # Changes of parameter node are observed so that whenever parameters are changed by a script or any other module
        # those are reflected immediately in the GUI.
        if self._parameterNode is not None:
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)
        self._parameterNode = inputParameterNode
        if self._parameterNode is not None:
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self.updateGUIFromParameterNode)

        # Initial GUI update
        self.updateGUIFromParameterNode()

    def updateGUIFromParameterNode(self, caller=None, event=None):
        """
        This method is called whenever parameter node is changed.
        The module GUI is updated to show the current state of the parameter node.
        """

        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        # Make sure GUI changes do not call updateParameterNodeFromGUI (it could cause infinite loop)
        self._updatingGUIFromParameterNode = True

        # Update node selectors and sliders
        self.ui.inputVolumeSelector.setCurrentNode(self._parameterNode.GetNodeReference("InputVolume"))
        task = self._parameterNode.GetParameter("Task")
        self.ui.taskComboBox.setCurrentIndex(self.ui.taskComboBox.findData(task))

        self.ui.cpuCheckBox.checked = self._parameterNode.GetParameter("CPU") == "true"
        self.ui.useStandardSegmentNamesCheckBox.checked = self._parameterNode.GetParameter("UseStandardSegmentNames") == "true"
        self.ui.outputSegmentationSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputSegmentation"))
        self.ui.outputCordSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputCord"))
        self.ui.outputCanalSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputCanal"))
        self.ui.outputLevelsSelector.setCurrentNode(self._parameterNode.GetNodeReference("OutputLevels"))
        self.ui.isoCheckBox.checked = self._parameterNode.GetParameter("Iso") == "true"
        self.ui.localizerVolumeSelector.setCurrentNode(self._parameterNode.GetNodeReference("LocalizerVolume"))

        # Update buttons states and tooltips
        inputVolume = self._parameterNode.GetNodeReference("InputVolume")
        if inputVolume:
            self.ui.applyButton.toolTip = _("Start segmentation")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.toolTip = _("Select input volume")
            self.ui.applyButton.enabled = False

        if inputVolume:
            task = self._parameterNode.GetParameter("Task")
            # Default to TotalSpineSeg
            base = "TotalSpineSeg"
            if task == "total":
                base = "TotalSpineSeg_step2"
            elif task == "step1":
                base = "TotalSpineSeg_step1"
            
            self.ui.outputSegmentationSelector.baseName = base
            self.ui.outputCordSelector.baseName = base + "_cord"
            self.ui.outputCanalSelector.baseName = base + "_canal"
            self.ui.outputLevelsSelector.baseName = base + "_levels"



        # All the GUI updates are done
        self._updatingGUIFromParameterNode = False

    def updateParameterNodeFromGUI(self, caller=None, event=None):
        """
        This method is called when the user makes any change in the GUI.
        The changes are saved into the parameter node (so that they are restored when the scene is saved and loaded).
        """

        if self._parameterNode is None or self._updatingGUIFromParameterNode:
            return

        wasModified = self._parameterNode.StartModify()  # Modify all properties in a single batch

        self._parameterNode.SetNodeReferenceID("InputVolume", self.ui.inputVolumeSelector.currentNodeID)
        self._parameterNode.SetParameter("Task", self.ui.taskComboBox.currentData)

        self._parameterNode.SetParameter("CPU", "true" if self.ui.cpuCheckBox.checked else "false")
        self._parameterNode.SetParameter("UseStandardSegmentNames", "true" if self.ui.useStandardSegmentNamesCheckBox.checked else "false")
        self._parameterNode.SetNodeReferenceID("OutputSegmentation", self.ui.outputSegmentationSelector.currentNodeID)
        self._parameterNode.SetParameter("Iso", "true" if self.ui.isoCheckBox.checked else "false")
        self._parameterNode.SetNodeReferenceID("OutputCord", self.ui.outputCordSelector.currentNodeID)
        self._parameterNode.SetNodeReferenceID("OutputCanal", self.ui.outputCanalSelector.currentNodeID)
        self._parameterNode.SetNodeReferenceID("OutputLevels", self.ui.outputLevelsSelector.currentNodeID)

        self._parameterNode.EndModify(wasModified)

    def onSelect(self):
        self.ui.applyButton.enabled = self.ui.inputVolumeSelector.currentNode() and (
            self.ui.outputSegmentationSelector.currentNode() or 
            self.ui.outputCordSelector.currentNode() or 
            self.ui.outputCanalSelector.currentNode() or 
            self.ui.outputLevelsSelector.currentNodeID
        )

    def onApplyButton(self):
        """
        Run processing when user clicks "Apply" button.
        """
        self.ui.statusLabel.plainText = ''

        import qt

        sequenceBrowserNode = slicer.modules.sequences.logic().GetFirstBrowserNodeForProxyNode(self.ui.inputVolumeSelector.currentNode())
        if sequenceBrowserNode:
            if not slicer.util.confirmYesNoDisplay(_("The input volume you provided are part of a sequence. Do you want to segment all frames of that sequence?")):
                sequenceBrowserNode = None

        try:
            slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
            self.logic.setupPythonRequirements()
            slicer.app.restoreOverrideCursor()
        except Exception as e:
            slicer.app.restoreOverrideCursor()
            import traceback
            traceback.print_exc()
            self.ui.statusLabel.appendPlainText(_("Failed to install Python dependencies:\n{exception}\n").format(exception=e))
            return

        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):

            # Create new segmentation node, if not selected yet
            if not self.ui.outputSegmentationSelector.currentNode() and \
               not self.ui.outputCordSelector.currentNode() and \
               not self.ui.outputCanalSelector.currentNode() and \
               not self.ui.outputLevelsSelector.currentNode():
                self.ui.outputSegmentationSelector.addNode()

            self.logic.useStandardSegmentNames = self.ui.useStandardSegmentNamesCheckBox.checked

            # Compute output
            self.logic.process(self.ui.inputVolumeSelector.currentNode(), 
                               self.ui.outputSegmentationSelector.currentNode(),
                               outputCord=self.ui.outputCordSelector.currentNode(),
                               outputCanal=self.ui.outputCanalSelector.currentNode(),
                               outputLevels=self.ui.outputLevelsSelector.currentNode(), 
                               cpu=self.ui.cpuCheckBox.checked, 
                               iso=self.ui.isoCheckBox.checked,
                               localizerVolume=self.ui.localizerVolumeSelector.currentNode(),
                               task=self.ui.taskComboBox.currentData, 
                               interactive = True, 
                               sequenceBrowserNode = sequenceBrowserNode)

        self.ui.statusLabel.appendPlainText("\n" + _("Processing finished."))

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
        """Append text to log window
        """
        self.ui.statusLabel.appendPlainText(text)
        slicer.app.processEvents()  # force update


#
# TotalSpineSegLogic
#

class InstallError(Exception):
    def __init__(self, message, restartRequired=False):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self.message = message
        self.restartRequired = restartRequired
    def __str__(self):
        return self.message

class TotalSpineSegLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self):
        """
        Called when the logic class is instantiated. Can be used for initializing member variables.
        """
        from collections import OrderedDict

        ScriptedLoadableModuleLogic.__init__(self)

        self.totalSpineSegPythonPackageDownloadUrl = "https://github.com/neuropoly/totalspineseg/archive/master.zip"

        # Custom applications can set custom location for weights.
        # For example, it could be set to `sysconfig.get_path('scripts')` to have an independent copy of
        # the weights for each Slicer installation. However, setting such custom path would result in extra downloads and
        # storage space usage if there were multiple Slicer installations on the same computer.
        self.totalSpineSegWeightsPath = None

        self.logCallback = None
        self.clearOutputFolder = True
        self.useStandardSegmentNames = False
        self.pullMaster = False

        # List of property type codes that are specified by in the TotalSpineSeg terminology.
        #
        # # Codes are stored as a list of strings containing coding scheme designator and code value of the property type,
        # separated by "^" character. For example "SCT^123456".
        #
        # If property the code is found in this list then the TotalSpineSeg terminology will be used,
        # otherwise the DICOM terminology will be used. This is necessary because the DICOM terminology
        # does not contain all the necessary items and some items are incomplete (e.g., don't have color or 3D Slicer label).
        #
        self.totalSpineSegTerminologyPropertyTypes = []

        # Map from TotalSpineSeg structure name to terminology string.
        self.totalSpineSegLabelTerminology = {}

        # Segmentation tasks
        self.tasks = OrderedDict()
        self.tasks['total'] = {'title': 'Total Spine Segmentation (Step 2)', 'modalities': ['CT', 'MR'], 'supportsMultiLabel': True}
        self.tasks['step1'] = {'title': 'Step 1 Only', 'modalities': ['CT', 'MR'], 'supportsMultiLabel': True}

    def loadTotalSpineSegLabelTerminology(self):
        """
        Load terminology mapping.
        For TotalSpineSeg, we currently reference internal mapping in applyTotalSpineSegTerminology.
        This method is kept for compatibility or future extension.
        """
        pass




    def isMultiLabelSupportedForTask(self, task):
        return (task in self.tasks) and ('supportsMultiLabel' in self.tasks[task]) and self.tasks[task]['supportsMultiLabel']



    def getSegmentLabelColor(self, terminologyEntryStr):
        """Get segment label and color from terminology"""

        def labelColorFromTypeObject(typeObject, typeModifierObject=None):
            if typeModifierObject is not None:
                if typeModifierObject.GetSlicerLabel():
                    # Slicer label is specified for the modifier that includes the full name, use that
                    label = typeModifierObject.GetSlicerLabel()
                else:
                    # Slicer label is not specified, assemble label from type and modifier
                    typeLabel = typeObject.GetSlicerLabel() if typeObject.GetSlicerLabel() else typeObject.GetCodeMeaning()
                    label = f"{typeLabel} {typeModifierObject.GetCodeMeaning()}"
                rgb = typeModifierObject.GetRecommendedDisplayRGBValue()
                if rgb[0] == 127 and rgb[1] == 127 and rgb[2] == 127:
                    # Type modifier did not have color specified, try to use the color of the type
                    rgb = typeObject.GetRecommendedDisplayRGBValue()
                return label, (rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
            label = typeObject.GetSlicerLabel() if typeObject.GetSlicerLabel() else typeObject.GetCodeMeaning()
            rgb = typeObject.GetRecommendedDisplayRGBValue()
            return label, (rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)

        tlogic = slicer.modules.terminologies.logic()

        terminologyEntry = slicer.vtkSlicerTerminologyEntry()
        if not tlogic.DeserializeTerminologyEntry(terminologyEntryStr, terminologyEntry):
            raise RuntimeError(_("Failed to deserialize terminology string: {terminology_entry_str}").format(terminology_entry_str=terminologyEntryStr))

        numberOfTypes = tlogic.GetNumberOfTypesInTerminologyCategory(terminologyEntry.GetTerminologyContextName(), terminologyEntry.GetCategoryObject())
        foundTerminologyEntry = slicer.vtkSlicerTerminologyEntry()
        for typeIndex in range(numberOfTypes):
            tlogic.GetNthTypeInTerminologyCategory(terminologyEntry.GetTerminologyContextName(), terminologyEntry.GetCategoryObject(), typeIndex, foundTerminologyEntry.GetTypeObject())
            if terminologyEntry.GetTypeObject().GetCodingSchemeDesignator() != foundTerminologyEntry.GetTypeObject().GetCodingSchemeDesignator():
                continue
            if terminologyEntry.GetTypeObject().GetCodeValue() != foundTerminologyEntry.GetTypeObject().GetCodeValue():
                continue
            if terminologyEntry.GetTypeModifierObject() and terminologyEntry.GetTypeModifierObject().GetCodeValue():
                # Type has a modifier, get the color from there
                numberOfModifiers = tlogic.GetNumberOfTypeModifiersInTerminologyType(terminologyEntry.GetTerminologyContextName(), terminologyEntry.GetCategoryObject(), terminologyEntry.GetTypeObject())
                foundMatchingModifier = False
                for modifierIndex in range(numberOfModifiers):
                    tlogic.GetNthTypeModifierInTerminologyType(terminologyEntry.GetTerminologyContextName(), terminologyEntry.GetCategoryObject(), terminologyEntry.GetTypeObject(),
                        modifierIndex, foundTerminologyEntry.GetTypeModifierObject())
                    if terminologyEntry.GetTypeModifierObject().GetCodingSchemeDesignator() != foundTerminologyEntry.GetTypeModifierObject().GetCodingSchemeDesignator():
                        continue
                    if terminologyEntry.GetTypeModifierObject().GetCodeValue() != foundTerminologyEntry.GetTypeModifierObject().GetCodeValue():
                        continue
                    return labelColorFromTypeObject(foundTerminologyEntry.GetTypeObject(), foundTerminologyEntry.GetTypeModifierObject())
                continue
            return labelColorFromTypeObject(foundTerminologyEntry.GetTypeObject())

        raise RuntimeError(f"Color was not found for terminology {terminologyEntryStr}")

    def log(self, text):
        logging.info(text)
        if self.logCallback:
            self.logCallback(text)

    def installedTotalSpineSegPythonPackageDownloadUrl(self):
        """Get package download URL of the installed TotalSpineSeg Python package"""
        import importlib.metadata
        import json
        try:
            metadataPath = [p for p in importlib.metadata.files('totalspineseg') if 'direct_url.json' in str(p)][0]
            with open(metadataPath.locate()) as json_file:
                data = json.load(json_file)
            return data['url']
        except:
            # Failed to get version information, probably not installed from download URL
            return None

    def installedTotalSpineSegPythonPackageInfo(self):
        import shutil
        import subprocess
        versionInfo = subprocess.check_output([shutil.which('PythonSlicer'), "-m", "pip", "show", "totalspineseg"]).decode()

        # Get download URL, as the version information does not contain the github hash
        downloadUrl = self.installedTotalSpineSegPythonPackageDownloadUrl()
        if downloadUrl:
            versionInfo += "Download URL: " + downloadUrl

        return versionInfo

    def simpleITKPythonPackageVersion(self):
        """Utility function to get version of currently installed SimpleITK.
        Currently not used, but it can be useful for diagnostic purposes.
        """

        import shutil
        import subprocess
        versionInfo = subprocess.check_output([shutil.which('PythonSlicer'), "-m", "pip", "show", "SimpleITK"]).decode()

        # versionInfo looks something like this:
        #
        #   Name: SimpleITK
        #   Version: 2.2.0rc2.dev368
        #   Summary: SimpleITK is a simplified interface to the Insight Toolkit (ITK) for image registration and segmentation
        #   ...
        #

        # Get version string (second half of the second line):
        version = versionInfo.split('\n')[1].split(' ')[1].strip()
        return version

    def pipInstallSelective(self, packageToInstall, installCommand, packagesToSkip):
        """Installs a Python package, skipping a list of packages.
        Return the list of skipped requirements (package name with version requirement).
        """
        slicer.util.pip_install(f"{installCommand} --no-deps")
        skippedRequirements = []  # list of all missed packages and their version

        # Get path to site-packages\nnunetv2-2.2.dist-info\METADATA
        import importlib.metadata
        metadataPath = [p for p in importlib.metadata.files(packageToInstall) if 'METADATA' in str(p)][0]
        metadataPath.locate()

        # Remove line: `Requires-Dist: SimpleITK (==2.0.2)`
        # User Latin-1 encoding to read the file, as it may contain non-ASCII characters and not necessarily in UTF-8 encoding.
        filteredMetadata = ""
        with open(metadataPath.locate(), "r+", encoding="latin1") as file:
            for line in file:
                skipThisPackage = False
                requirementPrefix = 'Requires-Dist: '
                if line.startswith(requirementPrefix):
                    for packageToSkip in packagesToSkip:
                        if packageToSkip in line:
                            skipThisPackage = True
                            break
                if skipThisPackage:
                    # skip SimpleITK requirement
                    skippedRequirements.append(line.removeprefix(requirementPrefix))
                    continue
                filteredMetadata += line
            # Update file content with filtered result
            file.seek(0)
            file.write(filteredMetadata)
            file.truncate()

        # Install all dependencies but the ones listed in packagesToSkip
        import importlib.metadata
        requirements = importlib.metadata.requires(packageToInstall)
        for requirement in requirements:
            skipThisPackage = False
            for packageToSkip in packagesToSkip:
                if requirement.startswith(packageToSkip):
                    # Do not install
                    skipThisPackage = True
                    break

            match = False
            if not match:
                # Rewrite optional depdendencies info returned by importlib.metadata.requires to be valid for pip_install:
                # Requirement Original: ruff; extra == "dev"
                # Requirement Rewritten: ruff
                match = re.match(r"([\S]+)[\s]*; extra == \"([^\"]+)\"", requirement)
                if match:
                    requirement = f"{match.group(1)}"
            if not match:
                # nibabel >=2.3.0 -> rewrite to: nibabel>=2.3.0
                match = re.match(r"([\S]+)[\s](.+)", requirement)
                if match:
                    requirement = f"{match.group(1)}{match.group(2)}"

            if skipThisPackage:
                self.log(_('- Skip {requirement}').format(requirement=requirement))
            else:
                self.log(_('- Installing {requirement}...').format(requirement=requirement))
                slicer.util.pip_install(requirement)

        return skippedRequirements

    def setupPythonRequirements(self, upgrade=False):
        import importlib.metadata
        import importlib.util
        import packaging

        # TotalSpineSeg requires this, yet it is not listed among its dependencies
        try:
            import pandas
        except ModuleNotFoundError as e:
            slicer.util.pip_install("pandas")

        # TotalSpineSeg requires dicom2nifti (we don't use any DICOM features in Slicer but DICOM support is not optional in TotalSpineSeg)
        # but latest dicom2nifti is broken on Python-3.9. We need to install an older version.
        # (dicom2nifti was recently updated to version 2.6. This version needs pydicom >= 3.0.0, which requires python >= 3.10)
        try:
            import dicom2nifti
        except ModuleNotFoundError as e:
            slicer.util.pip_install("dicom2nifti<=2.5.1")

        # These packages come preinstalled with Slicer and should remain unchanged
        packagesToSkip = [
            'SimpleITK',  # Slicer's SimpleITK uses a special IO class, which should not be replaced
            'torch',  # needs special installation using SlicerPyTorch
            'nnunetv2',  # needs special installation using SlicerNNUNet
            'requests',  # TotalSpineSeg would want to force a specific version of requests, which would require a restart of Slicer and it is unnecessary
            'rt_utils',  # Only needed for RTSTRUCT export, which is not needed in Slicer; rt_utils depends on opencv-python which is hard to build
            'dicom2nifti', # We already installed a known working version, do not let TotalSpineSeg to upgrade to a newer version that may not work on Python-3.9
            ]

        # Ask for confirmation before installing PyTorch and nnUNet
        confirmPackagesToInstall = []

        try:
          import PyTorchUtils
        except ModuleNotFoundError as e:
          raise InstallError("This module requires PyTorch extension. Install it from the Extensions Manager.")

        minimumTorchVersion = "2.0.0"
        torchLogic = PyTorchUtils.PyTorchUtilsLogic()
        if not torchLogic.torchInstalled():
            confirmPackagesToInstall.append("PyTorch")

        try:
            import SlicerNNUNetLib
        except ModuleNotFoundError as e:
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

        # Install PyTorch
        if "PyTorch" in confirmPackagesToInstall:
            self.log(_('PyTorch Python package is required. Installing... (it may take several minutes)'))
            torch = torchLogic.installTorch(askConfirmation=False, torchVersionRequirement = f">={minimumTorchVersion}")
            if torch is None:
                raise InstallError("This module requires PyTorch extension. Install it from the Extensions Manager.")
        else:
            # torch is installed, check version
            from packaging import version
            if version.parse(torchLogic.torch.__version__) < version.parse(minimumTorchVersion):
                raise InstallError(f'PyTorch version {torchLogic.torch.__version__} is not compatible with this module.'
                                 + f' Minimum required version is {minimumTorchVersion}. You can use "PyTorch Util" module to install PyTorch'
                                 + f' with version requirement set to: >={minimumTorchVersion}')

        # Install nnUNet
        if "nnunetv2" in confirmPackagesToInstall:
            self.log(_('nnunetv2 package is required. Installing... (it may take several minutes)'))
            nnunet = nnunetlogic.setupPythonRequirements(f"nnunetv2>={minimumNNUNetVersion}")
            if not nnunet:
                raise InstallError("This module requires SlicerNNUNet extension. Install it from the Extensions Manager.")
        else:
            installed_nnunet_version = nnunetlogic.getInstalledNNUnetVersion()
            if installed_nnunet_version < version.parse(minimumNNUNetVersion):
                raise InstallError(f'nnUNetv2 version {installed_nnunet_version} is not compatible with this module.'
                                 + f' Minimum required version is {minimumNNUNetVersion}. You can use "nnUNet" module to install nnUNet'
                                 + f' with version requirement set to: >={minimumNNUNetVersion}')

        # Install TotalSpineSeg
        needToInstall = False
        try:
            import totalspineseg
        except ImportError:
            needToInstall = True

        if needToInstall or upgrade:
            self.log(_('TotalSpineSeg is required. Installing... (it may take several minutes)'))
            slicer.util.pip_install("totalspineseg[nnunetv2] --upgrade" if upgrade else "totalspineseg[nnunetv2]")
            self.log(_('TotalSpineSeg installation completed successfully.'))


    def setDefaultParameters(self, parameterNode):
        """
        Initialize parameter node with default settings.
        """
        if not parameterNode.GetParameter("Task"):
            parameterNode.SetParameter("Task", "total")
        if not parameterNode.GetParameter("UseStandardSegmentNames"):
            parameterNode.SetParameter("UseStandardSegmentNames", "true")

    def logProcessOutput(self, proc, returnOutput=False):
        # Wait for the process to end and forward output to the log
        output = ""
        from subprocess import CalledProcessError
        while True:
            try:
                line = proc.stdout.readline()
                if not line:
                    break
                if returnOutput:
                    output += line
                self.log(line.rstrip())
            except UnicodeDecodeError as e:
                # Code page conversion happens because `universal_newlines=True` sets process output to text mode,
                # and it fails because probably system locale is not UTF8. We just ignore the error and discard the string,
                # as we only guarantee correct behavior if an UTF8 locale is used.
                pass

        proc.wait()
        retcode = proc.returncode
        if retcode != 0:
            raise CalledProcessError(retcode, proc.args, output=proc.stdout, stderr=proc.stderr)
        return output if returnOutput else None



    def process(self, inputVolume, outputSegmentation, outputCord=None, outputCanal=None, outputLevels=None, cpu=False, iso=False, localizerVolume=None, task='total', interactive=False, sequenceBrowserNode=None):
        # Input Volume validation
        if not inputVolume:
            raise ValueError("Input volume is invalid")
        
        # At least one output must be selected? 
        if not outputSegmentation and not outputCord and not outputCanal and not outputLevels:
             raise ValueError("At least one output segmentation must be selected")

        import time
        startTime = time.time()

        # Create new empty folder
        import os
        import shutil
        tempFolder = slicer.util.tempDirectory()

        # Input file must be .nii or .nii.gz
        inputFile = os.path.join(tempFolder, "input.nii")
        outputSegmentationFolder = os.path.join(tempFolder, "output")
        os.makedirs(outputSegmentationFolder, exist_ok=True)

        self.log(_("Writing input file to {input_file}").format(input_file=inputFile))
        volumeStorageNode = slicer.mrmlScene.CreateNodeByClass("vtkMRMLVolumeArchetypeStorageNode")
        volumeStorageNode.SetFileName(inputFile)
        volumeStorageNode.UseCompressionOff()
        volumeStorageNode.WriteData(inputVolume)
        volumeStorageNode.UnRegister(None)

        # Get Python executable path
        import shutil
        pythonSlicerExecutablePath = shutil.which('PythonSlicer')
        if not pythonSlicerExecutablePath:
             raise RuntimeError("Python was not found")

        # Construct command
        # totalspineseg INPUT OUTPUT
        cmd = [pythonSlicerExecutablePath, "-m", "totalspineseg.inference", inputFile, outputSegmentationFolder]

        if cpu:
            cmd.extend(["--device", "cpu"])

        if iso:
            cmd.append("--iso")

        if localizerVolume:
            import tempfile
            localizerPath = os.path.join(tempFolder, "localizer.nii.gz")
            slicer.util.saveNode(localizerVolume, localizerPath)
            cmd.append("--loc")
            cmd.append(localizerPath)

        if task == 'step1':
            cmd.append("--step1")
            
        # Efficiency: Use keep-only to skip unnecessary steps
        keep_only = []
        if outputCord:
            keep_only.append('step1_cord')
        if outputCanal:
            keep_only.append('step1_canal')
        if outputLevels:
            keep_only.append('step1_levels')
        
        # Main output handling
        if outputSegmentation:
            if task == 'total':
                keep_only.append('step2_output')
            elif task == 'step1':
                keep_only.append('step1_output')

        if keep_only:
             cmd.append("--keep-only")
             cmd.extend(keep_only)

        self.log(_('Creating segmentations with TotalSpineSeg AI...'))
        self.log(f"Processing started (Task: {task}, Keep: {keep_only})...")
        self.log(_("TotalSpineSeg arguments: {options}").format(options=cmd))

        proc = slicer.util.launchConsoleProcess(cmd)
        self.logProcessOutput(proc)

        self.log(_('Importing segmentation results...'))
        
        
        seen_nodes = set()

        def importResult(outputNode, subfolder, prefix, extractLabels=None, applyTerm=False, isSoft=False):
             if not outputNode: return
             self.log(f"Attempting to import {prefix} from {subfolder}...")
             self.log(f"Attempting to import {prefix} from {subfolder}...")
             
             # Don't clear if we've already written to this node in this session
             should_clear = outputNode.GetID() not in seen_nodes
             seen_nodes.add(outputNode.GetID())

             dirPath = os.path.join(outputSegmentationFolder, subfolder)
             if os.path.exists(dirPath):
                 if isSoft:
                     self.readProbMapVolume(outputNode, dirPath, prefix, colorNodeID=extractLabels, clear=should_clear)
                 else:
                     self.readSegmentationFolder(outputNode, dirPath, prefix, extractLabels=extractLabels, applyTerminology=applyTerm, clear=should_clear)
                     self.setSourceVolume(outputNode, inputVolume) # setSourceVolume works for SegNode
             else:
                 self.log(f"Warning: Output folder {subfolder} not found. Segmentation skipped.")

        # Load Main Segmentation
        if outputSegmentation:
            targetFolder = "step2_output" if task == 'total' else "step1_output"
            importResult(outputSegmentation, targetFolder, "TotalSpineSegOutput", applyTerm=not self.useStandardSegmentNames)

        # Load Spinal Cord
        # Use step1_cord which contains soft segmentation of cord.
        if outputCord:
             # Cord is label 1 in the soft segmentation
             # Use Green for Cord
             importResult(outputCord, "step1_cord", "TotalSpineSegCord", extractLabels="vtkMRMLColorTableNodeGreen", isSoft=True) 

        # Load Spinal Canal
        if outputCanal:
             # Use Yellow or Cyan for Canal
             importResult(outputCanal, "step1_canal", "TotalSpineSegCanal", extractLabels="vtkMRMLColorTableNodeYellow", isSoft=True)

        # Load Levels
        if outputLevels:
             importResult(outputLevels, "step1_levels", "TotalSpineSegLevels", applyTerm=False)

        stopTime = time.time()
        self.log(_("Processing completed in {time_elapsed:.2f} seconds").format(time_elapsed=stopTime-startTime))
        
        # Visibility Logic
        # "by default make all but main seg not visible unless user do not want the main seg"
        # Ensure Input Volume is Background
        slicer.util.setSliceViewerLayers(background=inputVolume)
        
        if outputSegmentation:
             # Main segmentation exists, so it is shown (Slicer default).
             # Hide other volumes to prevent clutter
             # Access logic of Views? Slicer doesn't auto-show Volumes in FG unless selected.
             # But if we just loaded them, they might be active?
             # Just ensures they are NOT in FG.
             pass 
        else:
             # Main segmentation is None.
             # User might want to see Cord or Canal.
             # If Cord exists, show it in Foreground?
             if outputCord:
                  slicer.util.setSliceViewerLayers(foreground=outputCord, foregroundOpacity=0.5)
             elif outputCanal:
                  slicer.util.setSliceViewerLayers(foreground=outputCanal, foregroundOpacity=0.5)

        if self.clearOutputFolder:
            if os.path.isdir(tempFolder):
                shutil.rmtree(tempFolder)

    def setSourceVolume(self, segmentationNode, volumeNode):
        segmentationNode.SetNodeReferenceID(segmentationNode.GetReferenceImageGeometryReferenceRole(), volumeNode.GetID())
        segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
        
        shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
        inputVolumeShItem = shNode.GetItemByDataNode(volumeNode)
        studyShItem = shNode.GetItemParent(inputVolumeShItem)
        segmentationShItem = shNode.GetItemByDataNode(segmentationNode)
        if segmentationShItem and inputVolumeShItem:
             currentParent = shNode.GetItemParent(segmentationShItem)
             if currentParent != studyShItem:
                 shNode.SetItemParent(segmentationShItem, studyShItem)

    def readSegmentationFolder(self, outputSegmentation, output_segmentation_dir, name_prefix, extractLabels=None, applyTerminology=True, clear=True):
        if clear:
             outputSegmentation.GetSegmentation().RemoveAllSegments()
        
        import glob
        nii_files = glob.glob(os.path.join(output_segmentation_dir, "*.nii.gz")) + glob.glob(os.path.join(output_segmentation_dir, "*.nii"))
        
        if not nii_files:
            self.log(_("No output files found in {dir}").format(dir=output_segmentation_dir))
            return
            
        labelVolumePath = nii_files[0]
        self.log(_("Importing {file}").format(file=labelVolumePath))
        
        labelmapVolumeNode = slicer.util.loadLabelVolume(labelVolumePath, {"name": name_prefix, "show": False})
        
        # Import everything first
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, outputSegmentation)
        
        if extractLabels:
            # We want to import ONLY specific labels
            segmentation = outputSegmentation.GetSegmentation()
            # Iterate and remove unwanted
            for i in range(segmentation.GetNumberOfSegments() - 1, -1, -1):
                segId = segmentation.GetNthSegmentID(i)
                segment = segmentation.GetSegment(segId)
                try:
                    # Parse from NAME, not ID
                    name = segment.GetName()
                    val = None
                    try:
                        val = int(name)
                    except ValueError:
                         import re
                         nums = re.findall(r'\d+', name)
                         if nums:
                             val = int(nums[-1])
                    
                    if val is not None and val not in extractLabels:
                        segmentation.RemoveSegment(segId)
                except ValueError:
                    continue
        
        if applyTerminology:
             self.log("Applying terminology...")
             self.applyTotalSpineSegTerminology(outputSegmentation)
        else:
             self.log("Skipping terminology application.")
        
        # Cleanup
        slicer.mrmlScene.RemoveNode(labelmapVolumeNode)

    def readProbMapVolume(self, outputVolume, output_dir, name_prefix, colorNodeID=None, clear=True):
        """
        Imports soft segmentation (probability map) as a scalar volume and configures display.
        """
        import glob
        nii_files = glob.glob(os.path.join(output_dir, "*.nii.gz")) + glob.glob(os.path.join(output_dir, "*.nii"))
        
        if not nii_files:
            self.log(_("No output files found in {dir}").format(dir=output_dir))
            return

        filePath = nii_files[0]
        self.log(_("Importing probability map {file}").format(file=filePath))
        
        # Load volume into the existing node (update it)
        tempNode = slicer.util.loadVolume(filePath, {"name": name_prefix + "_Temp", "show": False})
        if not tempNode:
            self.log("Failed to load volume")
            return
            
        import vtk
        
        # Deep copy image data to decouple from reader pipeline
        newImageData = vtk.vtkImageData()
        newImageData.DeepCopy(tempNode.GetImageData())
        
        outputVolume.SetAndObserveImageData(newImageData)
        outputVolume.CopyOrientation(tempNode)
        outputVolume.SetOrigin(tempNode.GetOrigin())
        outputVolume.SetSpacing(tempNode.GetSpacing())
        
        directionMatrix = vtk.vtkMatrix4x4()
        tempNode.GetIJKToRASDirectionMatrix(directionMatrix)
        outputVolume.SetIJKToRASDirectionMatrix(directionMatrix)
        
        slicer.mrmlScene.RemoveNode(tempNode)
        
        # Configure Display
        displayNode = outputVolume.GetDisplayNode()
        if not displayNode:
             outputVolume.CreateDefaultDisplayNodes()
             displayNode = outputVolume.GetDisplayNode()
        
        displayNode.SetApplyThreshold(True)
        displayNode.SetLowerThreshold(0.01)
        
        if colorNodeID:
            displayNode.SetAndObserveColorNodeID(colorNodeID)



    def applyTotalSpineSegTerminology(self, outputSegmentation):
        segmentation = outputSegmentation.GetSegmentation()
        
        # Mapping from TotalSpineSeg label IDs to segment names
        # Based on inference.py and README
        mapping = {
            1: "spinal_cord",
            2: "spinal_canal",
            3: "vertebrae_L5", 
            # Note: The mapping in TotalSpineSeg seems to vary by usage. 
            # Standard map based on inference.py label_texts_right/left:
            # Right (Vertebrae/Cord/Canal)
            11: "vertebrae_C1", 12: "vertebrae_C2", 13: "vertebrae_C3", 14: "vertebrae_C4", 15: "vertebrae_C5", 16: "vertebrae_C6", 17: "vertebrae_C7",
            21: "vertebrae_T1", 22: "vertebrae_T2", 23: "vertebrae_T3", 24: "vertebrae_T4", 25: "vertebrae_T5", 26: "vertebrae_T6", 27: "vertebrae_T7", 28: "vertebrae_T8", 29: "vertebrae_T9", 30: "vertebrae_T10", 31: "vertebrae_T11", 32: "vertebrae_T12",
            41: "vertebrae_L1", 42: "vertebrae_L2", 43: "vertebrae_L3", 44: "vertebrae_L4", 45: "vertebrae_L5", 46: "vertebrae_L6",
            50: "sacrum",
            # Left (IVDs)
            63: "disc_C2_C3", 64: "disc_C3_C4", 65: "disc_C4_C5", 66: "disc_C5_C6", 67: "disc_C6_C7", 70: "disc_C7_T1", 
            71: "disc_T1_T2", 72: "disc_T2_T3", 73: "disc_T3_T4", 74: "disc_T4_T5", 75: "disc_T5_T6", 76: "disc_T6_T7", 77: "disc_T7_T8", 78: "disc_T8_T9", 79: "disc_T9_T10", 80: "disc_T10_T11", 81: "disc_T11_T12",
            91: "disc_T12_L1", 92: "disc_L1_L2", 93: "disc_L2_L3", 94: "disc_L3_L4", 95: "disc_L4_L5", 100: "disc_L5_S1"
        }
        
        for i in range(segmentation.GetNumberOfSegments()):
            segmentId = segmentation.GetNthSegmentID(i)
            segment = segmentation.GetSegment(segmentId)
            
            segmentName = segment.GetName()
            self.log(f"Processing segment {i}: Name='{segmentName}', ID='{segmentId}'")
            
            # Helper to extract label value
            labelValue = None
            try:
                # Try parsing the name directly if it is a number "1"
                labelValue = int(segmentName)
            except ValueError:
                # Try to parse from string like "Label_1" or "TotalSpineSeg_step2_Label_1"
                # using re.findall to get all numbers and taking the LAST one.
                import re
                numbers = re.findall(r'\d+', segmentName)
                if numbers:
                    labelValue = int(numbers[-1])
            
            if labelValue is not None and labelValue in mapping:
                self.log(f"Renaming segment '{segmentName}' (ID: {segmentId}) -> Value: {labelValue} -> {mapping[labelValue]}")
                segment.SetName(mapping[labelValue])
            else:
                self.log(f"Mapping failed for segment '{segmentName}' (ID: {segmentId}). Parsed Value: {labelValue}. In Mapping: {labelValue in mapping if labelValue else 'None'}")


#
# TotalSpineSegTest
#

class TotalSpineSegTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """ Do whatever is needed to reset the state - typically a scene clear will be enough.
        """
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here.
        """
        self.setUp()
        self.test_TotalSpineSeg1()

    def test_TotalSpineSeg1(self):
        """ Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        self.delayDisplay("Starting the test")

        # Get/create input data
        import SampleData
        # Using MRHead (MRI) as it is smaller and more relevant for TotalSpineSeg than CTACardio
        inputVolume = SampleData.downloadSample('MRHead')
        self.delayDisplay('Loaded test data set')

        outputSegmentation = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLSegmentationNode')

        # Test the module logic

        # Logic testing is disabled by default to not overload automatic build machines (pytorch is a huge package and computation
        # on CPU takes 5-10 minutes). Set testLogic to True to enable testing.
        # To run the test:
        # 1. Open Slicer
        # 2. Go to "Reload & Test" module (or use Module search) or Developer Tools -> Extension Wizard -> Select Extension -> Edit -> Test
        # 3. Or simply switch to TotalSpineSeg module, then click "Reload and Test" button in the "Reload & Test" area (if enabled in Developer mode)
        # 4. Modify 'testLogic = True' below to actually run the inference during the test.
        testLogic = False

        if testLogic:
            logic = TotalSpineSegLogic()
            
            self.delayDisplay('Set up required Python packages')
            logic.setupPythonRequirements()

            self.delayDisplay('Compute output')
            # Using step1 as it is faster for testing
            logic.process(inputVolume, outputSegmentation, task='step1')

        else:
            logging.warning("test_TotalSpineSeg1 logic testing was skipped. Set 'testLogic = True' in the code to run the full inference test.")

        self.delayDisplay('Test passed')


