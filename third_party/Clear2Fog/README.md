# Clear2Fog

Clear2Fog (C2F) is a multimodal fog simulation pipeline built to address the data scarcity of foggy weather data in autonomous driving datasets. It transforms standard clear-weather data into consistent fog across both camera and LiDAR sensors.

Rather than just applying simple image filters, C2F combines a physics-based atmospheric scattering model with a novel atmospheric light estimation method to avoid chromatic biases and structural artefacts. This repository contains the framework used for our research on synthetic data efficiency.


### Key Features

* Generates synchronised fog across camera and LiDAR data, and can also support camera-only or LiDAR-only data
* Implements an atmospheric scattering model with a novel atmospheric light estimation method to eliminate chromatic biases
* Allows setting user-defined fog density via a visibility parameter input
* Tested beyond autonomous driving datasets, including COCO and Flickr30k
* Get started in three simple steps: (1) create the environment from the .yml file, (2) download the required pre-trained model and (3) run the pipeline

---
### Getting Started

#### 1. Setup Environment

Clone this repository and create the Conda environment from the provided file. This will install all necessary dependencies.

```bash
git clone https://github.com/mmohamed28/Clear2Fog
cd Clear2Fog
conda env create -f environment.yml
conda activate c2f
```

#### 2. Download Pre-trained Models

This pipeline relies on the Depth Pro model. Please download the following checkpoint and place it in the specified directory:

* Depth Pro: Download ```depth_pro.pt``` from [ml-depth-pro](https://github.com/apple/ml-depth-pro/blob/main/get_pretrained_models.sh) and place it in ```./src/fog_pipeline/depth_map/depth_pro/checkpoints/```

#### 3. Demo
You are now ready to run the pipeline. You can use the following command as a template:

```bash
python c2f.py \
-c CAMERA_DIR \
-l LIDAR_DIR \
-o OUTPUT_DIR \
-v VIS_METRES
```
* ```-c```: Input folder containing the RGB files
* ```-l```: Input folder containing the ```.npy``` point cloud files
* ```-o```: Empty output folder to save the simulated files
* ```-v```: Visibility distance in metres, controlling fog density (lower values = denser fog)

---
### Acknowledgments and Dependencies
This project builds upon the excellent work of many other researchers. The ```LICENSES``` folder contains the full license for each of the third-party models used.

* Depth Pro: [https://github.com/apple/ml-depth-pro](https://github.com/apple/ml-depth-pro)
* LiDAR Fog Simulation: [https://github.com/MartinHahner/LiDAR-Fog-Simulation](https://github.com/MartinHahner/LiDAR_fog_sim)
* WaymoCOCO: [https://github.com/shinya7y/WaymoCOCO](https://github.com/shinya7y/WaymoCOCO)

---
### Citation
If you find this repository or our findings useful, please cite our paper:

```bibtex
@article{mohamed2026clear2fog,
  title     = {A data efficiency study of synthetic fog for object detection using the Clear2Fog pipeline},
  author    = {Mohamed, Mohamed Ahmed and Huang, Xiaowei},
  journal   = {Neurocomputing},
  volume    = {703},
  pages     = {134798},
  year      = {2026},
  publisher = {Elsevier},
  doi       = {10.1016/j.neucom.2026.134798}
}
```
