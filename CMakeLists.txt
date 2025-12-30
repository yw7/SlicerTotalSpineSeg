cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(SlicerTotalSpineSeg)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/yw7/SlicerTotalSpineSeg")
set(EXTENSION_CATEGORY "Segmentation")
set(EXTENSION_CONTRIBUTORS "Dr. Yehuda Warszawer")
set(EXTENSION_DESCRIPTION "3D Slicer extension for automatic spine segmentation using TotalSpineSeg.")
set(EXTENSION_ICONURL "https://github.com/yw7/SlicerTotalSpineSeg/raw/main/TotalSpineSeg/Resources/Icons/TotalSpineSeg.png")
set(EXTENSION_SCREENSHOTURLS "https://github.com/user-attachments/assets/ae7d69fb-9742-4490-9a21-864f7a569389")
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
