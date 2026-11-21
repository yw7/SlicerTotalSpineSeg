cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(TotalSpineSeg)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/yw7/SlicerTotalSpineSeg")
set(EXTENSION_CATEGORY "Segmentation")
set(EXTENSION_CONTRIBUTORS "Dr. Yehuda Warszawer")
set(EXTENSION_DESCRIPTION "3D Slicer extension for fully automatic segmentation of vertebrae, intervertebral discs, spinal cord and spinal canal in MRI and CT images using the TotalSpineSeg AI model. License: LGPL-3.0.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/yw7/SlicerTotalSpineSeg/main/TotalSpineSeg/Resources/Icons/TotalSpineSeg.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/yw7/SlicerTotalSpineSeg/main/Screenshot01.jpg")
set(EXTENSION_DEPENDS "PyTorch NNUNet")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(TotalSpineSeg)

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
