cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(TotalSpineSeg)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/yw7/SlicerTotalSpineSeg")
set(EXTENSION_CATEGORY "Segmentation")
set(EXTENSION_CONTRIBUTORS "Yihao Wang")
set(EXTENSION_DESCRIPTION "Fully automatic total spine instance segmentation in 3D Slicer using TotalSpineSeg AI model.")
set(EXTENSION_ICONURL "https://raw.githubusercontent.com/yw7/SlicerTotalSpineSeg/main/TotalSpineSeg.png")
set(EXTENSION_SCREENSHOTURLS "https://raw.githubusercontent.com/yw7/SlicerTotalSpineSeg/main/Screenshot01.jpg")
set(EXTENSION_DEPENDS "PyTorch")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(TotalSpineSeg)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
