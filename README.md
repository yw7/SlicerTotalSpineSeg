# TotalSpineSeg

3D Slicer extension for automatic spine segmentation using the [TotalSpineSeg AI model](https://github.com/neuropoly/totalspineseg).

## Acknowledgement

This extension is based on the [TotalSpineSeg](https://github.com/neuropoly/totalspineseg) tool developed by NeuroPoly.
It is adapted from the [SlicerTotalSegmentator](https://github.com/lassoan/SlicerTotalSegmentator) extension.

## Setup

1. **Install 3D Slicer**: Download and install the latest version of [3D Slicer](https://slicer.readthedocs.io/en/latest/user_guide/getting_started.html#installing-3d-slicer).
2. **Install Extension**: Install `TotalSpineSeg` extension via the Extension Manager (once available) or manually.
3. **GPU Setup (Recommended)**: A CUDA-capable GPU is highly recommended for fast processing. Ensure you have proper NVIDIA drivers installed.

## Usage

1. Open 3D Slicer.
2. Load a spine CT or MRI volume (`.nii`, `.nii.gz`, or DICOM).
3. Switch to the **TotalSpineSeg** module (under Segmentation).
4. Select the **Input Volume**.
5. Select or create an **Output Segmentation** node.
6. Choose the **Task** (default is "Total Spine Segmentation"). "Step 1 Only" runs a faster detection pass.
7. Click **Apply**.
   - On the first run, the module will download the necessary Python packages and model weights. This may take several minutes.
   - Subsequent runs will be faster.

## Features

- **Total Spine Segmentation**: Full segmentation of vertebrae, discs, spinal cord, and spinal canal.
- **Step 1 Only**: Runs only the detection/localization step (faster).

## Troubleshooting

- **First Run Delay**: The first run downloads large model files. Please be patient.
- **CUDA Errors**: Ensure your PyTorch installation matches your CUDA version. Use "PyTorch Util" module in Slicer to manage PyTorch installation if needed.
- **Memory Issues**: If you run out of memory, try cropping the volume using "Crop Volume" module before segmentation.
