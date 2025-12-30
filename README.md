# TotalSpineSeg

![Extension Screenshot](https://github.com/user-attachments/assets/ae7d69fb-9742-4490-9a21-864f7a569389)

3D Slicer extension for fully automatic spine MRI and CT segmentation using the [TotalSpineSeg AI model](https://github.com/neuropoly/totalspineseg).

## Acknowledgement

This extension is based on the [TotalSpineSeg](https://github.com/neuropoly/totalspineseg) tool developed by NeuroPoly.
It is adapted from the [SlicerTotalSegmentator](https://github.com/lassoan/SlicerTotalSegmentator) extension.

## Setup

1. **Install 3D Slicer**: Download and install the latest version of [3D Slicer](https://slicer.readthedocs.io/en/latest/user_guide/getting_started.html#installing-3d-slicer).
2. **Install Extension**:
    *   **Via Extension Manager**: Install `TotalSpineSeg` extension via the Extension Manager (once available).
    *   **Manual Installation**:
        1.  Download or clone this repository.
        2.  Open 3D Slicer.
        3.  Click on the search icon (magnifying glass) next to the Modules menu in the toolbar (or press `Ctrl+F`).
        4.  Search for **Extension Wizard** and open it.
        5.  Click on **Select Extension**.
        6.  Navigate to and select the `SlicerTotalSpineSeg` folder (the root folder of this repository).
        7.  Confirm that you want to load the extension.
3. **GPU Setup (Recommended)**: A CUDA-capable GPU is highly recommended for fast processing. Ensure you have proper NVIDIA drivers installed.

## Usage

1. Open 3D Slicer.
2. Load a spine MRI or CT volume (`.nii`, `.nii.gz`, or DICOM).
3. Switch to the **TotalSpineSeg** module (under Segmentation).
4. **Inputs**:
    - Select the **Input Volume**.
    - (Optional) Select a **Localizer** segmentation (Step 1 or Step 2 output). This is the output of the model on a localizer image, used to ensure accurate instance segmentation on short FOV scans that do not contain C1 or Sacrum.
5. **Outputs**:
    - Select or create output nodes for the desired segmentations:
        - **Step 2**: Segmentation of canal, cord, and instance segmentation of vertebrae and discs.
        - **Step 1**: Segmentation of canal, cord, vertebrae (binary), and instance segmentation of discs.
        - **Cord**: Spinal cord soft segmentation (probability map).
        - **Canal**: Spinal canal soft segmentation (probability map).
        - **Levels**: Single-voxel vertebral levels at the posterior tip of each disc (similar to SCT).
    - **Apply anatomical terminology**: Check this to rename segments to standard anatomical names (e.g., "vertebrae_C1").
    - **Isotropic output**: Check this to keep the output at 1mm³ resolution (as used by the model) instead of resampling back to input space.
6. Click **Apply**.
   - On the first run, the module will download the necessary Python packages and model weights. This may take several minutes.
   - Subsequent runs will be faster.

## Loading & Visualization

The **Load** tab allows you to easily load and visualize existing segmentation results.

1.  **Apply anatomical terminology**: If checked, loaded segmentation files will be automatically renamed to standard anatomical terms.
2.  **Load Buttons**: Use the `...` button next to each category (Step 2, Step 1, Levels, Cord, Canal) to load a file from disk.
3.  **Visibility Controls**:
    *   **Eye Icon**: Toggle 2D visibility in slice views.
    *   **3D Icon**: Toggle 3D surface rendering.
4.  **Selectors**: You can also select existing nodes from the scene to control their visibility.

## Features

- **Multi-Modality**: Supports both MRI and CT scans.
- **Comprehensive Segmentation**:
    - **Step 1**: Segmentation of spinal canal, spinal cord, vertebrae (binary), and instance segmentation of discs.
    - **Step 2**: Segmentation of canal, cord, and instance segmentation of vertebrae and discs.
    - **Localizer Support**: Use model outputs from localizer images to handle short FOV scans (missing C1 or Sacrum).
- **Anatomical Terminology**: Automatically renames segments to standard anatomical terms.

## Troubleshooting

- **First Run Delay**: The first run downloads large model files. Please be patient.
- **CUDA Errors**: Ensure your PyTorch installation matches your CUDA version. Use "PyTorch Util" module in Slicer to manage PyTorch installation if needed.
- **Memory Issues**: If you run out of memory, try cropping the volume using "Crop Volume" module before segmentation.
