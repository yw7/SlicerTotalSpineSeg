cmake_minimum_required(VERSION 3.0)

project(SlicerTotalSpineSeg)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/neuropoly/SlicerTotalSpineSeg")
set(EXTENSION_CATEGORY "Segmentation")
set(EXTENSION_CONTRIBUTORS "NeuroPoly (Polytechnique Montreal)")
set(EXTENSION_DESCRIPTION "3D Slicer extension for automatic spine segmentation using TotalSpineSeg.")
set(EXTENSION_ICONURL "https://github.com/neuropoly/SlicerTotalSpineSeg/raw/main/TotalSpineSeg/Resources/Icons/TotalSpineSeg.png")
set(EXTENSION_SCREENSHOTURLS "https://github.com/user-attachments/assets/b4c85ce8-c59b-4ab1-b02a-37638c9ac375")
set(EXTENSION_DEPENDS "NA")
set(EXTENSION_BUILD_SUBDIRECTORY ".")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(TotalSpineSeg)
