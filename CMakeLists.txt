cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(SlicerTotalSpineSeg)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/yw7/SlicerTotalSpineSeg")
set(EXTENSION_CATEGORY "Segmentation")
set(EXTENSION_CONTRIBUTORS "Dr. Yehuda Warszawer")
set(EXTENSION_DESCRIPTION "3D Slicer extension for automatic spine segmentation using TotalSpineSeg.")
set(EXTENSION_ICONURL "https://github.com/yw7/SlicerTotalSpineSeg/raw/main/TotalSpineSeg/Resources/Icons/TotalSpineSeg.png")
set(EXTENSION_SCREENSHOTURLS "https://github.com/user-attachments/assets/db6eee8d-6a15-4d0e-a0ea-be03e9d3e504")
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
