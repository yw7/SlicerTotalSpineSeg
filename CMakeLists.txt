cmake_minimum_required(VERSION 3.0)

project(SlicerTotalSpineSeg)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://github.com/neuropoly/SlicerTotalSpineSeg")
set(EXTENSION_CATEGORY "Segmentation")
set(EXTENSION_CONTRIBUTORS "NeuroPoly (Polytechnique Montreal)")
set(EXTENSION_DESCRIPTION "3D Slicer extension for automatic spine segmentation using TotalSpineSeg.")
set(EXTENSION_ICONURL "https://github.com/neuropoly/SlicerTotalSpineSeg/raw/main/TotalSpineSeg/Resources/Icons/TotalSpineSeg.png")
set(EXTENSION_SCREENSHOTURLS "https://github.com/user-attachments/assets/a42b324c-dc82-4b1b-ad3b-0fdb4d0d3fc5 https://github.com/user-attachments/assets/700d114a-8358-41e4-afaa-09e94ee3a2e5")
set(EXTENSION_DEPENDS "NA")
set(EXTENSION_BUILD_SUBDIRECTORY ".")

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(TotalSpineSeg)
