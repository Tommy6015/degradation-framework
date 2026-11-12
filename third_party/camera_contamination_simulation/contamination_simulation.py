


#### Import needed Libs
import numpy as np
import cv2
import matplotlib.pyplot as plt
import random

from PIL import Image
from scipy import ndimage
from scipy.special import binom

import torch
import torch.nn as nn
import torch.nn.functional as F

from noise import pnoise2


# How the network output is mapped onto an image of any size
# ----------------------------------------------------------
# The training masks were square (defisheyed WoodScape images, centre-cropped to 966x966) and
# resized to 64x64, so the network output has 1:1 geometry: a round droplet is round.
# To keep shapes undistorted on a non-square image (H x W), the 64x64 output is scaled
# uniformly to a square of side max(H, W) and the centre H x W part is cut out ("cover").
# The user's x, y are positions in the image; image_to_model_xy converts them to positions in
# that square, so every image position is reachable. size stays relative to the longer side,
# as in training (size / max(shape)). For square images all of this is the identity.

def image_to_model_xy(x, y, height, width):
    """
    Converts normalized image coordinates (x: column / width, y: row / height) to the
    network's coordinates in the max(height, width) square that is centre-cropped to the image.
    """
    side = max(height, width)
    x_model = 0.5 + (x - 0.5) * width / side
    y_model = 0.5 + (y - 0.5) * height / side
    return x_model, y_model


def render_mask(mask, height, width, blur_kernel_size, blur_sigma, return_square=False):
    """
    Scales the 64x64 network output uniformly to a max(height, width) square, applies the
    Gaussian blur, and returns the centre (height x width) crop. Blurring before cropping
    avoids border artifacts where a shape continues beyond the image edge.

    :param blur_kernel_size: Odd kernel size, as int or (k, k) tuple.
    :param return_square: If True, return (crop, square, top, left): the uncropped square too,
                          with the crop's offset in it (used to measure shapes cut by the image edge).
    """
    height, width = int(height), int(width)
    side = max(height, width)
    square = cv2.resize(mask, (side, side), interpolation=cv2.INTER_LINEAR)
    if isinstance(blur_kernel_size, (int, np.integer)):
        blur_kernel_size = (blur_kernel_size, blur_kernel_size)
    square = cv2.GaussianBlur(square, tuple(blur_kernel_size), blur_sigma)
    top, left = (side - height) // 2, (side - width) // 2
    crop = square[top:top + height, left:left + width]
    if return_square:
        return crop, square, top, left
    return crop


def to_rgb(img_array):
    """
    Converts an image to 3 channels: grayscale (H, W) or (H, W, 1) is replicated, RGBA (H, W, 4)
    drops its alpha channel. 3-channel images are returned unchanged.
    """
    if img_array.ndim == 2 or img_array.shape[2] == 1:
        return cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
    if img_array.shape[2] == 4:
        return cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
    return img_array


######################################################################################################### Model
# Define the new model structure with latent noise
class ShapeGeneratorModel(nn.Module):
    def __init__(self, noise_dim=100):
        super(ShapeGeneratorModel, self).__init__()
        self.noise_dim = noise_dim
        
        # Linear layers, input dimension includes noise + structured input (x, y, size)
        self.fc1 = nn.Linear(3 + noise_dim, 256)
        self.fc2 = nn.Linear(256, 512)
        
        # Output size to match input for ConvTranspose layers
        self.fc3 = nn.Linear(512, 16 * 16 * 64)
        
        # Transposed convolution layers to upsample to 64x64
        self.conv_transpose1 = nn.ConvTranspose2d(64, 64, kernel_size=3, stride=2, padding=1, output_padding=1)
        self.conv_transpose2 = nn.ConvTranspose2d(64, 32, kernel_size=3, stride=2, padding=1, output_padding=1)
        self.conv_transpose3 = nn.Conv2d(32, 1, kernel_size=3, padding=1)
        
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, xy_size):
        # Generate random noise
        batch_size = xy_size.size(0)
        z = torch.randn(batch_size, self.noise_dim, device=xy_size.device)
        
        # Concatenate structured input (x, y, size) with noise
        x = torch.cat([xy_size, z], dim=1)
        
        # Pass through fully connected layers
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        x = self.relu(self.fc3(x))
        
        # Reshape to fit into ConvTranspose layers
        x = x.view(-1, 64, 16, 16)  # Reshape to (batch_size, channels, height, width)
        
        # Upsample to 64x64 using ConvTranspose layers
        x = self.relu(self.conv_transpose1(x))  # 32x32
        x = self.relu(self.conv_transpose2(x))  # 64x64
        x = self.sigmoid(self.conv_transpose3(x))  # Final binary mask (64x64)
        
        return x







######################################################################################################### Total
class OpaqueContaminationGenerator:
    def __init__(self, model_path):
        # Check if a GPU is available and set the device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f'Using device: {self.device}')
        
        # Initialize and load the model
        self.model = ShapeGeneratorModel().to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()  # Set the model to evaluation mode



    # Update the generate_mask function to work with the new model
    def generate_mask(self, x, y, size, blur_kernel_size, blur_sigma, height=960, width=960):
        """
        Generates a mask based on the input x, y, size values and applies Gaussian Blur.

        :param x: Horizontal position in the image, 0..1 (column / width).
        :param y: Vertical position in the image, 0..1 (row / height).
        :param size: Size of the mask, relative to the longer image side.
        :param blur_kernel_size: The size of the Gaussian kernel. Must be odd (default is (15, 15)).
        :param blur_sigma: Standard deviation for Gaussian kernel. If 0, it is computed automatically.
        :param height: Height of the output mask in pixels (default 960).
        :param width: Width of the output mask in pixels (default 960).
        :return: Tuple containing the original 64x64 mask and the resized (height x width) mask with blur applied.
        """
        # x, y are positions in the image; convert them to the network's square coordinates
        x_model, y_model = image_to_model_xy(x, y, height, width)

        # Convert the input into a tensor and move to the correct device (GPU/CPU)
        input_tensor = torch.tensor([[x_model, y_model, size]], dtype=torch.float32).to(self.device)

        # Generate the mask with the new model
        with torch.no_grad():
            output_mask = self.model(input_tensor)

        # Remove batch and channel dimensions
        output_mask = output_mask[0, 0].cpu().numpy()  # Convert to numpy array (64x64)

        # Scale uniformly to a max(height, width) square, blur, and centre-crop to the image size
        blurred_mask = render_mask(output_mask, height, width, blur_kernel_size, blur_sigma)

        return output_mask, blurred_mask


        


    def apply_mask_to_image(self, img_array, x, y, size, mask_color=(0, 0, 0), blur_kernel_size=(15, 15), blur_sigma=0):
        """
        Applies the generated mask to the given image array, with an option to specify the mask color.

        :param img_array: Input image array of any size (the output has the same size)
        :param x: Horizontal position in the image, 0..1 (column / width)
        :param y: Vertical position in the image, 0..1 (row / height)
        :param size: Size of the mask, relative to the longer image side
        :param mask_color: Color of the mask (default is black). Should be a tuple (R, G, B).
        :param blur_kernel_size: The size of the Gaussian kernel. Must be odd (default is (15, 15)).
        :param blur_sigma: Standard deviation for Gaussian kernel. If 0, it is computed automatically.
        :return: Contaminated image with the mask applied
        """
        # Keep the input's own size; grayscale images are converted to 3-channel RGB
        img_resized = to_rgb(img_array)
        height, width = img_resized.shape[:2]

        # Generate the mask at the image size
        _, resized_mask = self.generate_mask(x, y, size, blur_kernel_size, blur_sigma, height, width)

        # Normalize mask to range [0, 1]
        resized_mask_normalized = resized_mask.astype(np.float32)

        # Create a mask color array, matching the shape of the image
        mask_color_array = np.ones_like(img_resized, dtype=np.float32)
        mask_color_array[:, :] = mask_color  # Set the mask color

        # Apply the mask: blend the image with the mask color using the opacity from the resized mask
        contaminated_image = img_resized * (1 - resized_mask_normalized[:, :, np.newaxis]) + \
                            mask_color_array * resized_mask_normalized[:, :, np.newaxis]

        # Ensure the values stay in the range [0, 255] and convert to uint8
        contaminated_image = np.clip(contaminated_image, 0, 255).astype(np.uint8)

        return contaminated_image, resized_mask_normalized


    def TESTapply_mask_to_image_twoc(self, img_array, x, y, size, color_start=(0, 0, 0), color_end=(181, 101, 29), blur_kernel_size=(15, 15), blur_sigma=0):
        """
            Applies the generated mask to the given image array using a gradient between two RGB colors.
        
        :param img_array: Input image array of any size (the output has the same size)
        :param x: Horizontal position in the image, 0..1 (column / width)
        :param y: Vertical position in the image, 0..1 (row / height)
        :param size: Size of the mask, relative to the longer image side
        :param color_start: Start color for the mask gradient (RGB tuple)
        :param color_end: End color for the mask gradient (RGB tuple)
        :param blur_kernel_size: The size of the Gaussian kernel. Must be odd (default is (15, 15)).
        :param blur_sigma: Standard deviation for Gaussian kernel. If 0, it is computed automatically.
        :return: Contaminated image with the gradient mask applied
        """
        # Keep the input's own size; grayscale images are converted to 3-channel RGB
        img_resized = to_rgb(img_array)
        height, width = img_resized.shape[:2]

        # Generate the mask at the image size
        _, resized_mask = self.generate_mask(x, y, size, blur_kernel_size, blur_sigma, height, width)

        # Normalize mask to range [0, 1]
        resized_mask_normalized = resized_mask.astype(np.float32)

        # Create a mask color array using linear interpolation between color_start and color_end
        mask_color_array = np.zeros_like(img_resized, dtype=np.float32)
        
        for i in range(3):  # Iterate through the RGB channels
            mask_color_array[:, :, i] = color_start[i] + (color_end[i] - color_start[i]) * resized_mask_normalized

        # Apply the mask: blend the image with the interpolated mask color using the opacity from the resized mask
        contaminated_image = img_resized * (1 - resized_mask_normalized[:, :, np.newaxis]) + \
                            mask_color_array * resized_mask_normalized[:, :, np.newaxis]
        
        # Ensure the values stay in the range [0, 255] and convert to uint8
        contaminated_image = np.clip(contaminated_image, 0, 255).astype(np.uint8)
        
        return contaminated_image, resized_mask_normalized



    def apply_mask_to_image_twoc(self, img_array, x, y, size, color_start=(0, 0, 0), color_end=(181, 101, 29), blur_kernel_size=(15, 15), blur_sigma=0, gamma=0.5):
        """
        Applies the generated mask to the given image array using a gradient between two RGB colors, 
        with a non-linear adjustment to bias towards the first color.
        
        :param img_array: Input image array of any size (the output has the same size)
        :param x: Horizontal position in the image, 0..1 (column / width)
        :param y: Vertical position in the image, 0..1 (row / height)
        :param size: Size of the mask, relative to the longer image side
        :param color_start: Start color for the mask gradient (RGB tuple)
        :param color_end: End color for the mask gradient (RGB tuple)
        :param blur_kernel_size: The size of the Gaussian kernel. Must be odd (default is (15, 15)).
        :param blur_sigma: Standard deviation for Gaussian kernel. If 0, it is computed automatically.
        :param gamma: Exponent for non-linear adjustment of the mask (default is 0.5).
                    Values < 1 bias towards the first color, values > 1 bias towards the second color.
        :return: Contaminated image with the gradient mask applied
        """
        # Keep the input's own size; grayscale images are converted to 3-channel RGB
        img_resized = to_rgb(img_array)
        height, width = img_resized.shape[:2]

        # Generate the mask at the image size
        _, resized_mask = self.generate_mask(x, y, size, blur_kernel_size, blur_sigma, height, width)

        # Normalize mask to range [0, 1]
        resized_mask_normalized = resized_mask.astype(np.float32)

        # Apply non-linear transformation to bias towards color_start
        color_weights = resized_mask_normalized ** gamma

        # Create a mask color array using linear interpolation between color_start and color_end
        mask_color_array = np.zeros_like(img_resized, dtype=np.float32)
        
        for i in range(3):  # Iterate through the RGB channels
            mask_color_array[:, :, i] = color_start[i] + (color_end[i] - color_start[i]) * color_weights

        # Apply the mask: blend the image with the interpolated mask color using the opacity from the resized mask
        contaminated_image = img_resized * (1 - resized_mask_normalized[:, :, np.newaxis]) + \
                            mask_color_array * resized_mask_normalized[:, :, np.newaxis]
        
        # Ensure the values stay in the range [0, 255] and convert to uint8
        contaminated_image = np.clip(contaminated_image, 0, 255).astype(np.uint8)
        
        return contaminated_image, resized_mask_normalized




######################################################################################################### Semi
class SemiContaminationGenerator:
    def __init__(self, model_path):
        # Check if a GPU is available and set the device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f'Using device: {self.device}')
        
        # Initialize and load the model
        self.model = ShapeGeneratorModel().to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()  # Set the model to evaluation mode



    def generate_perlin_noise(self, width, height, scale=10):
        """
        Generates a Perlin noise texture of given width and height.
        
        :param width: Width of the noise texture.
        :param height: Height of the noise texture.
        :param scale: Scale of the Perlin noise (affects the level of detail).
        :return: Generated Perlin noise as a 2D NumPy array.
        """
        perlin_noise = np.zeros((height, width))
        for i in range(height):
            for j in range(width):
                perlin_noise[i][j] = pnoise2(i / scale, j / scale, octaves=6, persistence=0.5, lacunarity=2.0)
        
        # Normalize the Perlin noise to range [0, 1]
        perlin_noise = (perlin_noise - perlin_noise.min()) / (perlin_noise.max() - perlin_noise.min())
        return perlin_noise
    


    def generate_mask(self, x, y, size, blur_kernel_size=(15, 15), blur_sigma=0, height=960, width=960):
        """
        Generates a mask based on the input x, y, size values and applies Gaussian Blur.

        :param x: Horizontal position in the image, 0..1 (column / width).
        :param y: Vertical position in the image, 0..1 (row / height).
        :param size: Size of the mask, relative to the longer image side.
        :param blur_kernel_size: The size of the Gaussian kernel. Must be odd (default is (15, 15)).
        :param blur_sigma: Standard deviation for Gaussian kernel. If 0, it is computed automatically.
        :param height: Height of the output mask in pixels (default 960).
        :param width: Width of the output mask in pixels (default 960).
        :return: Tuple containing the original 64x64 mask and the resized (height x width) mask with blur applied.
        """
        # x, y are positions in the image; convert them to the network's square coordinates
        x_model, y_model = image_to_model_xy(x, y, height, width)

        # Convert the input into a tensor and move to the correct device (GPU/CPU)
        input_tensor = torch.tensor([[x_model, y_model, size]], dtype=torch.float32).to(self.device)
        
        # Generate the mask
        with torch.no_grad():
            output_mask = self.model(input_tensor)
        
        # Remove batch and channel dimensions
        output_mask = output_mask[0, 0].cpu().numpy()  # Convert to numpy array (64x64)
        
        # Scale uniformly to a max(height, width) square, blur, and centre-crop to the image size
        blurred_mask = render_mask(output_mask, height, width, blur_kernel_size, blur_sigma)

        return output_mask, blurred_mask


    ### Not in Operation
    # Goal was to shift the vaues and control the strength
    def sigmoid(self, x):
        return 1 / (1 + np.exp(-x))

    def shift_perlin_noise(self, perlin_noise, shift_factor=0.5):
        """
        Shifts the Perlin noise values closer to 1 by applying a linear transformation.

        :param perlin_noise: The generated Perlin noise array.
        :param shift_factor: The factor by which to shift the values closer to 1 (default is 0.5).
        :return: Perlin noise shifted closer to 1.
        """
        # Apply a linear shift to the noise values
        shifted_noise = perlin_noise * (1 - shift_factor) + shift_factor

        # Apply sigmoid transformation
        #shifted_noise = self.sigmoid(perlin_noise * shift_factor)
        
        return shifted_noise
    
    ###
    def apply_mask_with_perlin_noise(self, img_array, x, y, size, mask_color=(128, 128, 128), blur_kernel_size=(15, 15), blur_sigma=0, noise_scale=10):
        """
        Applies the generated mask to the given image array, embedding a Perlin noise texture in the mask with a specified color.

        :param img_array: Input image array of any size (the output has the same size)
        :param x: Horizontal position in the image, 0..1 (column / width)
        :param y: Vertical position in the image, 0..1 (row / height)
        :param size: Size of the mask, relative to the longer image side
        :param mask_color: Color of the mask, specified as an (R, G, B) tuple (default is gray: (128, 128, 128)).
        :param noise_scale: Scale of the Perlin noise (affects detail level of the noise)
        :param blur_kernel_size: The size of the Gaussian kernel. Must be odd (default is (15, 15)).
        :param blur_sigma: Standard deviation for Gaussian kernel. If 0, it is computed automatically.
        :return: Contaminated image with the Perlin noise mask applied
        """
        # Keep the input's own size; grayscale images are converted to 3-channel RGB
        img_resized = to_rgb(img_array)
        height, width = img_resized.shape[:2]

        # Generate the mask at the image size
        _, resized_mask = self.generate_mask(x, y, size, blur_kernel_size, blur_sigma, height, width)

        # Generate Perlin noise texture for the mask (same size as the image)
        perlin_noise = self.generate_perlin_noise(width, height, scale=noise_scale)

        # Normalize mask to range [0, 1]
        resized_mask_normalized = resized_mask.astype(np.float32)

        # Apply Perlin noise to the mask (blending with Perlin noise)
        noise_mask = resized_mask_normalized * perlin_noise

        # Create a mask color array, matching the shape of the image, and apply the specified mask color
        mask_color_array = np.ones_like(img_resized, dtype=np.float32)
        mask_color_array[:, :, 0] = mask_color[0]  # Red channel
        mask_color_array[:, :, 1] = mask_color[1]  # Green channel
        mask_color_array[:, :, 2] = mask_color[2]  # Blue channel

        # Apply the noise mask: blend the image with the mask color using noise as opacity
        contaminated_image = img_resized * (1 - noise_mask[:, :, np.newaxis]) + \
                            mask_color_array * noise_mask[:, :, np.newaxis]

        # Ensure the values stay in the range [0, 255] and convert to uint8
        contaminated_image = np.clip(contaminated_image, 0, 255).astype(np.uint8)

        return contaminated_image, resized_mask_normalized
    

    







######################################################################################################### DROPLET
class DropletGenerator():
    def __init__(self, img_width=None, img_height=None, num_channels=3, model_path=None):
        """
        :param img_width, img_height, num_channels: Optional. Kept for backward compatibility only;
            simulate_droplet now takes the size from each input image, so images of any size work.
        :param model_path: Path to the trained droplet shape model (.pth).
        """
        if model_path is None:
            raise ValueError("model_path is required, e.g. DropletGenerator(model_path='gen_models/best_model_droplet.pth')")

        # Check if a GPU is available and set the device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f'Using device: {self.device}')
        
        # Initialize and load the model
        self.model = ShapeGeneratorModel().to(self.device)
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()  # Set the model to evaluation mode

        # Init Vars
        self.img_width = img_width
        self.img_height = img_height
        self.num_channels = num_channels
        self.last_droplets = []  # filled by simulate_droplet: one dict per droplet (see find_droplets)



    def generate_mask(self, x, y, size, blur_kernel_size, blur_sigma, height=None, width=None, return_square=False):
        """
        Generates a mask based on the input x, y, size values and applies Gaussian Blur.

        :param x: Horizontal position in the image, 0..1 (column / width).
        :param y: Vertical position in the image, 0..1 (row / height).
        :param size: Size of the mask, relative to the longer image side.
        :param blur_kernel_size: The size of the Gaussian kernel. Must be odd (default is (15, 15)).
        :param blur_sigma: Standard deviation for Gaussian kernel. If 0, it is computed automatically.
        :param height: Height of the output mask in pixels (default: img_height given to the constructor).
        :param width: Width of the output mask in pixels (default: img_width given to the constructor).
        :param return_square: If True, return (mask, square, top, left) like render_mask.
        :return: The resized (height x width) mask with blur applied.
        """
        height = self.img_height if height is None else height
        width = self.img_width if width is None else width
        if height is None or width is None:
            raise ValueError("Give height and width, or img_width and img_height to the constructor.")
        # x, y are positions in the image; convert them to the network's square coordinates
        x_model, y_model = image_to_model_xy(x, y, height, width)

        # Convert the input into a tensor and move to the correct device (GPU/CPU)
        input_tensor = torch.tensor([[x_model, y_model, size]], dtype=torch.float32).to(self.device)
        
        # Generate the mask
        with torch.no_grad():
            output_mask = self.model(input_tensor)
        
        # Remove batch and channel dimensions
        output_mask = output_mask[0, 0].cpu().numpy()  # Convert to numpy array (64x64)
        
        # Scale uniformly to a max(height, width) square, blur, and centre-crop to the image size
        return render_mask(output_mask, height, width, blur_kernel_size, blur_sigma, return_square)
    




    class Segment():
        """BEZIER Curve Calculation"""
        def __init__(self, p1, p2, angle1, angle2, **kw):
            self.p1 = p1; self.p2 = p2
            self.angle1 = angle1; self.angle2 = angle2
            self.numpoints = kw.get("numpoints", 100)
            r = kw.get("r", 0.3)
            d = np.sqrt(np.sum((self.p2-self.p1)**2))
            self.r = r*d
            self.p = np.zeros((4,2))
            self.p[0,:] = self.p1[:]
            self.p[3,:] = self.p2[:]
            self.calc_intermediate_points(self.r)

        def bezier(self, points, num=200):
            bernstein = lambda n, k, t: binom(n,k)* t**k * (1.-t)**(n-k)

            N = len(points)
            t = np.linspace(0, 1, num=num)
            curve = np.zeros((num, 2))
            for i in range(N):
                curve += np.outer(bernstein(N - 1, i, t), points[i])
            return curve

        def calc_intermediate_points(self,r):
            self.p[1,:] = self.p1 + np.array([self.r*np.cos(self.angle1),
                                        self.r*np.sin(self.angle1)])
            self.p[2,:] = self.p2 + np.array([self.r*np.cos(self.angle2+np.pi),
                                        self.r*np.sin(self.angle2+np.pi)])
            self.curve = self.bezier(self.p,self.numpoints)


    def get_curve(self, points, **kw):
        """Bezier Curve"""
        segments = []
        for i in range(len(points)-1):
            seg = self.Segment(points[i,:2], points[i+1,:2], points[i,2],points[i+1,2],**kw)
            segments.append(seg)
        curve = np.concatenate([s.curve for s in segments])
        return segments, curve


    def get_bezier_curve(self, a, rad=0.2, edgy=0):
        """ given an array of points *a*, create a curve through
        those points. 
        
        *rad* is a number between 0 and 1 to steer the distance of
            control points.
            
        *edgy* is a parameter which controls how "edgy" the curve is,
            edgy=0 is smoothest."""
        p = np.arctan(edgy)/np.pi+.5
        a = self.ccw_sort(a)
        a = np.append(a, np.atleast_2d(a[0,:]), axis=0)
        d = np.diff(a, axis=0)
        ang = np.arctan2(d[:,1],d[:,0])
        f = lambda ang : (ang>=0)*ang + (ang<0)*(ang+2*np.pi)
        ang = f(ang)
        ang1 = ang
        ang2 = np.roll(ang,1)
        ang = p*ang1 + (1-p)*ang2 + (np.abs(ang2-ang1) > np.pi )*np.pi
        ang = np.append(ang, [ang[0]])
        a = np.append(a, np.atleast_2d(ang).T, axis=1)
        s, c = self.get_curve(a, r=rad, method="var")
        x,y = c.T
        return x,y, a

    def ccw_sort(self, p):
        """Clockwise Sorting"""
        d = p-np.mean(p,axis=0)
        s = np.arctan2(d[:,0], d[:,1])
        return p[np.argsort(s),:]


    def get_random_points(self, n=5, scale=0.8, mindst=None, rec=0):
        """ create n random points in the unit square, which are *mindst*
        apart, then scale them."""
        mindst = mindst or .7/n
        a = np.random.rand(n,2)
        d = np.sqrt(np.sum(np.diff(self.ccw_sort(a), axis=0), axis=1)**2)
        if np.all(d >= mindst) or rec>=200:
            return a*scale
        else:
            return self.get_random_points(n=n, scale=scale, mindst=mindst, rec=rec+1)


    #### Functions for Masking
    def sq_calc_bounds_white(self, img):
        """
        Find the by the Barrel Tranformation transformed Image in the transferred image

        Detailed description of the function explaining what it does.

        Parameters:
        img within transformed img with white background

        Returns:
        xmin, xmax, ymin, ymax (all Int's): Coordinated of the transformend img
        """
        height, width = img.shape[:2]
        xmin, xmax, ymin, ymax = 0, 0, 0, 0
        # Find xmin
        for i in range(height):
            if not np.all(img[i, :] == 255):
                xmin = i
                break
        # Find xmax
        for i in range(height-1, -1, -1):
            if not np.all(img[i, :] == 255):
                xmax = i
                break
        # Find ymin
        for j in range(width):
            if not np.all(img[:, j] == 255):
                ymin = j
                break
        # Find ymax
        for j in range(width-1, -1, -1):
            if not np.all(img[:, j] == 255):
                ymax = j
                break
        return xmin, xmax, ymin, ymax


        #### Functions for Masking
    def sq_calc_bounds_black(self, img):
        """
        like sq_calc_bounds_white but with black background
        """
        height, width = img.shape[:2]

        xmin, xmax, ymin, ymax = 0, 0, 0, 0

        # Find xmin
        for i in range(height):
            if not np.all(img[i, :] == 0):
                xmin = i
                break
        # Find xmax
        for i in range(height-1, -1, -1):
            if not np.all(img[i, :] == 0):
                xmax = i
                break
        # Find ymin
        for j in range(width):
            if not np.all(img[:, j] == 0):
                ymin = j
                break
        # Find ymax
        for j in range(width-1, -1, -1):
            if not np.all(img[:, j] == 0):
                ymax = j
                break
        return xmin, xmax, ymin, ymax


    def barrel_distortion(self, img, strength, source=None, offset=(0, 0), return_valid=False):
        """
        Transform a given img with Barrel Transforation around a random center:
        output pixel at radius r samples the input at radius r + strength * r**3.

        Input:
        img as np.array (the region to distort)

        Parameters:
        strength (Double): Strength of the transformation (in 1/px^2)
        source (np.array, optional): Image to sample from instead of img, e.g. the full image that img
            was cut from. Samples outside img then show the real surrounding scene instead of black;
            only samples outside source itself repeat its border pixels.
        offset ((int, int)): (column, row) position of img inside source.
        return_valid (bool): Also return a boolean mask of the output pixels whose sample lies inside img.

        Returns:
        transformed img as np array (and the validity mask if return_valid)
        """

        # Init
        height, width = img.shape[:2]
        x, y = np.meshgrid(np.arange(width), np.arange(height))


        # min(10, ...) keeps the original range for regions of 10 px or more and avoids an empty range for tiny ones
        center_x = random.randint(min(10, width), width)
        center_y = random.randint(min(10, height), height)

        center = (center_x, center_y)



        # From Cartesian to Spherical 
        x = x - center[0]
        y = y - center[1]
        r = np.sqrt(x**2 + y**2)
        theta = np.arctan2(y, x)

        # Barrel-Transformation
        r_distorted = r + strength * r**3

        # Transform in Cartesian Coordinated
        x_distorted = r_distorted * np.cos(theta) + center[0]
        y_distorted = r_distorted * np.sin(theta) + center[1]

        # Samples that fall inside img (outside, the old code got black pixels from cv2.remap's constant border)
        valid = (x_distorted >= 0) & (x_distorted <= width - 1) & (y_distorted >= 0) & (y_distorted <= height - 1)

        # Interpolation of the disorted image
        if source is None:
            distorted_img = cv2.remap(img, x_distorted.astype(np.float32), y_distorted.astype(np.float32), interpolation=cv2.INTER_LINEAR)
        else:
            distorted_img = cv2.remap(source, (x_distorted + offset[0]).astype(np.float32), (y_distorted + offset[1]).astype(np.float32),
                                      interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        if return_valid:
            return distorted_img, valid
        return distorted_img


    def create_white_background(self, height, width):
        """ Create White Background """
        return np.ones((height, width, 3), dtype=np.uint8) * 255  # Füllen Sie die Matrix mit Weiß (255)


    #### User Functions
    def generate_form(self, rad, edgy, n):
        """
        Generates a form using random points and a Bézier curve.

        This function creates a form by first generating a set of random points and then 
        using those points to generate a Bézier curve. The characteristics of the curve 
        are controlled by the 'rad' and 'edgy' parameters.

        Parameters:
        rad (float): A parameter that influences the curvature or radius of the Bézier curve.
        edgy (float): A parameter that controls the sharpness or edginess of the curve.
        n (int): The number of random points to generate.

        Returns:
        tuple: A tuple containing two lists, x and y coordinates, which represent the Bézier curve.
        """
        #print("Start generating...")

        a = self.get_random_points(n=n, scale=1)
        x,y, _ = self.get_bezier_curve(a,rad=rad, edgy=edgy)
        return x,y


    def set_position_form(self, x, y, x_orgin_trans=None, y_orgin_trans=None, size_scale=None):
        """
        Sets the position and scale of a form on a canvas or image.

        This function adjusts the position and size of a form based on provided or randomized 
        translation and scaling values. If no values are provided for the translation or scaling, 
        the function generates random values to position and scale the form within the boundaries 
        of the canvas or image.

        Parameters:
        x (list or ndarray): The x-coordinates of the form's points.
        y (list or ndarray): The y-coordinates of the form's points.
        x_orgin_trans (int, optional): The x-coordinate translation for positioning the form. 
                                    If None, a random value is generated.
        y_orgin_trans (int, optional): The y-coordinate translation for positioning the form. 
                                    If None, a random value is generated.
        size_scale (int, optional): The scaling factor for resizing the form. 
                                    If None, a random value is generated.

        Returns:
        tuple: A tuple containing the transformed x and y coordinates of the form.
        """
        # No values given --> Random init
        if x_orgin_trans==None or y_orgin_trans==None or size_scale==None:
            print("No user defined positions and scaling, randomize...")
            x_orgin_trans = random.randint(10, 0.5*self.img_width-10)
            y_orgin_trans = random.randint(10, 0.5*self.img_height-10)
            size_scale = random.randint(10, 0.5*min(self.img_width, 0.5*self.img_height))

        # Control
        x = np.abs(x * size_scale + x_orgin_trans)
        y = np.abs(y * size_scale + y_orgin_trans)
        return x,y
        
        



    def deploy_zoomin(self, mask, sq_min_x, sq_max_x, sq_min_y, sq_max_y, sq_width, sq_height,
                    raw_img=None, 
                    b_strength=None,
                    ib_gauss_kernel = None,
                    blurr_roi_gauss_kernel=None,
                    mood='black',
                    test=False):

        """
        Deploys a form onto an image, applying barrel distortion, blurring, and blending effects.

        This function takes an input image and a form defined by its x and y coordinates. It then 
        applies a series of transformations, including barrel distortion, Gaussian blurring, and blending 
        with the original image, to create a composite image. The function also handles various 
        parameters such as the strength of the barrel distortion, the size of the Gaussian kernels for 
        blurring, and whether to perform the operations in 'test' mode, where intermediate results 
        are displayed.

        Parameters:
        raw_img (ndarray): The input image onto which the form will be deployed.
        form_x (list or ndarray): The x-coordinates of the form's points.
        form_y (list or ndarray): The y-coordinates of the form's points.
        barrel_strength_low (float, optional): The lower bound for the barrel distortion strength.
        barrel_strength_high (float, optional): The upper bound for the barrel distortion strength.
        ib_gauss_kernel (int, optional): The kernel size for the Gaussian blur applied to the blended image.
        blurr_roi_gauss_kernel (int, optional): The kernel size for the Gaussian blur applied to the region of interest (ROI).
        mask_blurr_gauss_kernel (int, optional): The kernel size for the Gaussian blur applied to the mask.
        mood (str, optional): 'white' fills the part of the distorted region whose samples lie outside the ROI
            with white; any other value (default 'black') shows the real surrounding scene there.
        test (bool, optional): If True, intermediate steps are visualized for debugging.

        Returns:
        ndarray: The fused image. If mask is None, image_b (the processed image before blending) instead.
        """

        ##### Step 1: Barrel Transformation
        """
        if b_strength is None and barrel_strength_low is None and barrel_strength_high is None:
            barrel_strength_low = 0.00000001
            barrel_strength_high = 0.0001
            
            # Init Parameters for Transformation
            barrel_strength = random.uniform(barrel_strength_low, barrel_strength_high)
        elif barrel_strength_low is not None and barrel_strength_high is not None:
            # Init Parameters for Transformation
            barrel_strength = random.uniform(barrel_strength_low, barrel_strength_high)

        else:
            barrel_strength = b_strength 
        """
        barrel_strength = b_strength 
        
        pre_roi = raw_img[sq_min_x:sq_max_x, sq_min_y:sq_max_y]




        ############################# TEST #############################
        if test:
            print("Pre_roi:  b_strength=", barrel_strength)
            plt.imshow(pre_roi)
            plt.axis('off')
            plt.axis('off')
            plt.show()
        ############################# TEST #############################

        # Do the transformation. Samples are taken from the full image, so pixels whose sample lies
        # outside the ROI show the real surrounding scene. (cv2.remap used to fill them with black,
        # and the black corners left in the crop below became dark spots inside the droplet.)
        distorted_roi, valid = self.barrel_distortion(pre_roi, barrel_strength, source=raw_img,
                                                      offset=(sq_min_y, sq_min_x), return_valid=True)
        ############################# TEST #############################
        if test:
            plt.imshow(distorted_roi)
            plt.axis('off')
            plt.axis('off')
            plt.show()
        ############################# TEST #############################




        ##### Step 2: Background
        # mood='white': the part sampled outside the ROI becomes white
        # (assumption: droplet is lighter than the raw_image because of lens effect).
        # Any other mood keeps the real surrounding scene there.
        if mood == 'white':
            distorted_roi[~valid] = 255

        # Crop to the bounding box of the part sampled inside the ROI; this sets the ZoomIn magnification.
        # Validity comes from the sample coordinates, not from pixel colour, so black scene content is kept.
        valid_rows, valid_cols = np.any(valid, axis=1), np.any(valid, axis=0)
        if valid_rows.any():
            prexmin, prexmax = int(np.argmax(valid_rows)), len(valid_rows) - int(np.argmax(valid_rows[::-1]))
            preymin, preymax = int(np.argmax(valid_cols)), len(valid_cols) - int(np.argmax(valid_cols[::-1]))
            prepre_roi = distorted_roi[prexmin:prexmax, preymin:preymax]
        else:
            prepre_roi = distorted_roi[:0, :0]  # nothing sampled inside the ROI: handled below

        if test:
            ############################# TEST #############################
            plt.imshow(prepre_roi)
            plt.axis('off')
            plt.axis('off')
            plt.show()
            ############################# TEST #############################



        ##### Step 3: Resize it of old roi
        # Case func calc_bounds found no bounds:
        # TODO: Not Nice
        if prepre_roi.shape[0] == 0 or prepre_roi.shape[1] == 0:
            print("Problem with resize.. Using only distroted:roi")
            content = distorted_roi
        else:
            content = cv2.resize(prepre_roi, ((sq_max_y-sq_min_y), (sq_max_x-sq_min_x)))
        ############################# TEST #############################
        if test:
            plt.imshow(content)
            plt.axis('off')
            plt.axis('off')
            plt.show()
        ############################# TEST #############################



        ##### Step 5: Apply Gaussian blur to ROI
        #if blurr_roi_gauss_kernel is None:
        #    blurr_roi_gauss_kernel = random.choice([11, 13, 15, 17, 19, 21, 23, 25])

        if blurr_roi_gauss_kernel == 0:
            blurred_content = content
        else:
            blurred_content = cv2.GaussianBlur(content, (blurr_roi_gauss_kernel, blurr_roi_gauss_kernel), 0)  # Adjust kernel size (15, 15) as needed


        ############################# TEST #############################
        if test:
            plt.imshow(blurred_content)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################



        ##### Step 6: Apply on old Image
        # Create I_B and blurr it
        #if ib_gauss_kernel is None:
        #    ib_gauss_kernel = 21

        image_b = raw_img.copy()
        image_b[sq_min_x:sq_max_x, sq_min_y:sq_max_y] = blurred_content


        
        ##### Step 7: Blur
        if ib_gauss_kernel > 0:
            image_b = cv2.GaussianBlur(image_b, (ib_gauss_kernel, ib_gauss_kernel), 0)  # Adjust kernel size (15, 15) as needed
        ############################# TEST #############################
        if test:
            print("Gauss Blurr I_B")
            plt.imshow(image_b)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################


        ###### Step 8: Generate
        if mask is None:  # caller blends itself (simulate_droplet, one image_b per droplet)
            return image_b
        fused_image=(mask*image_b[:,:,:]) + ((1-mask)*raw_img[:,:,:])
        #TIMfused_image = (mask*image_b[:,:,:]) + ((1-mask)*raw_img[:,:,:])
        fused_image = fused_image.astype(np.uint8)
        if test:
            ############################# TEST #############################   
            print("End of Simulation")
            plt.imshow(fused_image)
            plt.axis('off')
            plt.show()
            ############################# TEST #############################


        return fused_image
        



    def deploy_zoomout(self, mask, sq_min_x, sq_max_x, sq_min_y, sq_max_y, sq_width, sq_height,
                        raw_img=None, 
                        b_strength=None,
                        ib_gauss_kernel = None,
                        blurr_roi_gauss_kernel=None,
                        mood='black',
                        test=False):

        """
        Deploys a form onto an image, rotating and blurring a selected region.

        This function takes an input image and a form defined by its x and y coordinates. It then 
        applies a series of transformations, including rotation, resizing, Gaussian blurring, 
        and blending with the original image, to create a composite image. The function also handles 
        various parameters such as the size of the Gaussian kernels for blurring and whether to perform 
        the operations in 'test' mode, where intermediate results are displayed.

        Parameters:
        raw_img (ndarray): The input image onto which the form will be deployed.
        form_x (list or ndarray): The x-coordinates of the form's points.
        form_y (list or ndarray): The y-coordinates of the form's points.
        ib_gauss_kernel (int, optional): The kernel size for the Gaussian blur applied to the blended image.
        blurr_roi_gauss_kernel (int, optional): The kernel size for the Gaussian blur applied to the region of interest (ROI).
        mood (str, optional): The background color mode ('black' or 'white') for the distorted region. Default is 'black'.
        test (bool, optional): If True, intermediate steps are visualized for debugging.

        Returns:
        ndarray: The fused image. If mask is None, image_b (the processed image before blending) instead.
        """

        ##### Step 1: Extract Region of Interest (ROI)
        pre_roi = raw_img   #[sq_min_x:sq_max_x, sq_min_y:sq_max_y]
        ############################# TEST #############################
        if test:
            print("Original ROI:")
            plt.imshow(pre_roi)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################



        ##### Step 2: Rotate the ROI by 180 degrees
        rotated_roi = cv2.rotate(pre_roi, cv2.ROTATE_180)
        
        ############################# TEST #############################
        if test:
            print("Rotated ROI:")
            plt.imshow(rotated_roi)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################



        ##### Step 3: Resize it to a smaller version
        miniaturized_roi = cv2.resize(rotated_roi, (max(1, (sq_max_y-sq_min_y) // 2), max(1, (sq_max_x-sq_min_x) // 2)))
        ############################# TEST #############################
        if test:
            print("Miniaturized ROI:")
            plt.imshow(miniaturized_roi)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################



        ##### Step 4: Apply Gaussian blur to the resized ROI
        if blurr_roi_gauss_kernel == 0:
            blurred_content = miniaturized_roi
        else:
            blurred_content = cv2.GaussianBlur(miniaturized_roi, (blurr_roi_gauss_kernel, blurr_roi_gauss_kernel), 0)
        
        ############################# TEST #############################
        if test:
            print("Blurred Miniaturized ROI:")
            plt.imshow(blurred_content)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################



        ##### Step 5: Embed the blurred content back into the original image
        image_b = raw_img.copy()
        # Resize the blurred content to match the region size
        resized_blurred_content = cv2.resize(blurred_content, (sq_max_y - sq_min_y, sq_max_x - sq_min_x))
        image_b[sq_min_x:sq_max_x, sq_min_y:sq_max_y] = resized_blurred_content



        ##### Step 6: Apply Gaussian blur to the whole image
        if ib_gauss_kernel > 0:
            image_b = cv2.GaussianBlur(image_b, (ib_gauss_kernel, ib_gauss_kernel), 0)
        ############################# TEST #############################
        if test:
            print("Final Image:")
            plt.imshow(image_b)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################



        ###### Step 7: Generate the final image by blending with the original using the mask
        if mask is None:  # caller blends itself (simulate_droplet, one image_b per droplet)
            return image_b
        fused_image=(mask*image_b[:,:,:]) + ((1-mask)*raw_img[:,:,:])
        #fused_image = fused_image.astype(np.uint32)
        fused_image = fused_image.astype(np.uint8)
        
        ############################# TEST #############################   
        if test:
            print("End of Simulation:")
            plt.imshow(fused_image)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################
        return fused_image

            




    def simulate_droplet(self, f_C, raw_img, x, y, size,
                            mask_blurr_gauss_kernel=None, blur_sigma=0,
                            b_strength=None,
                            ib_gauss_kernel = None,
                            blurr_roi_gauss_kernel=None,
                            mood='black',
                            mask_threshold=0.5,
                            test=False):
        """
        Simulates a water droplet on raw_img (any size; grayscale/RGBA are converted to RGB).

        The network mask can contain several separate droplets. Each one is classified on its own
        (see find_droplets) and rendered as ZoomIn or ZoomOut inside its own bounding box; the results
        are blended with the original image using the soft mask. Details of the last call are in
        self.last_droplets.

        :param f_C: Camera focal length in px (for the resolution of raw_img). A droplet is rendered as
                    ZoomIn if its focal length f_D > f_C, otherwise as ZoomOut.
        :param mask_threshold: Mask value in [0, 1] from which a pixel counts as droplet when splitting
                    the mask into droplets and measuring them. The blending itself still uses the soft mask.
        :return: (fused_image, gt_mask) with gt_mask the soft network mask scaled to 0-255 (uint8).
        """
        # The image may have any size: take it from the input image (grayscale is converted to 3-channel RGB)
        raw_img = to_rgb(raw_img)
        img_height, img_width = raw_img.shape[:2]
        self.img_height, self.img_width = img_height, img_width  # also used by set_position_form

        # Create Mask with Model at the image size; the uncropped square is kept to measure droplets
        # that are cut by the image edge
        mask, mask_square, top, left = self.generate_mask(x, y, size, mask_blurr_gauss_kernel, blur_sigma,
                                                          img_height, img_width, return_square=True)

        # Ground truth: the soft mask as uint8; the blending mask is blurred once more
        gt_mask = np.uint8(mask * 255)
        mask = cv2.GaussianBlur(gt_mask, (mask_blurr_gauss_kernel, mask_blurr_gauss_kernel), 0)
        ############################# TEST #############################
        if test:
                print("GT-Mask:")
                plt.imshow(gt_mask)
                plt.axis('off')
                plt.colorbar()
                plt.show()
                print("Mask:")
                plt.imshow(mask)
                plt.axis('off')
                plt.colorbar()
                plt.show()
        ############################# TEST #############################

        # Split the mask into separate droplets; each one is classified on its own
        droplets, labels = self.find_droplets(mask_square, top, left, img_height, img_width, mask_threshold, f_C)
        self.last_droplets = droplets  # for inspection: bbox, size, f_D and case of every droplet
        if not droplets:
            return raw_img.copy(), np.zeros(raw_img.shape[:2], dtype=np.uint8)
        ############################# TEST #############################
        if test:
            print("Droplets (labels):")
            plt.imshow(labels)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################

        # Reshape mask to have the same number of dimensions as the RGB images
        mask = mask[:, :, np.newaxis]
        mask = mask / np.max(mask)      # Normalize Mask from [0,255] to [0,1]

        # With several droplets, every pixel (also the faint mask tail between droplets)
        # takes its content from the nearest droplet
        if len(droplets) > 1:
            _, (near_r, near_c) = ndimage.distance_transform_edt(labels == 0, return_indices=True)
            owner = labels[near_r, near_c]
            image_b = np.empty_like(raw_img)

        # OM Classifier: render every droplet as ZoomIn or ZoomOut (see find_droplets)
        ####################################################################################################################
        for i, d in enumerate(droplets, start=1):
            sq_min_x, sq_max_x, sq_min_y, sq_max_y = d['bbox']
            deploy = self.deploy_zoomin if d['case'] == 'ZoomIn' else self.deploy_zoomout
            droplet_b = deploy(None, sq_min_x, sq_max_x, sq_min_y, sq_max_y, sq_max_x - sq_min_x, sq_max_y - sq_min_y,
                               raw_img,
                               b_strength,
                               ib_gauss_kernel,
                               blurr_roi_gauss_kernel,
                               mood, test)
            if len(droplets) == 1:
                image_b = droplet_b
            else:
                own = owner == d['label']
                image_b[own] = droplet_b[own]
            print(f"Droplet {i}/{len(droplets)}: {d['size_px']} px{' (cut by image edge)' if d['cut'] else ''}, "
                  f"f_D = {d['f_D']:.0f} -> {d['case']}")

        # Blend with the original image using the soft mask
        fused_image = (mask*image_b[:,:,:]) + ((1-mask)*raw_img[:,:,:])
        fused_image = fused_image.astype(np.uint8)
        ############################# TEST #############################
        if test:
            print("End of Simulation:")
            plt.imshow(fused_image)
            plt.axis('off')
            plt.show()
        ############################# TEST #############################

        return fused_image, gt_mask


    def find_droplets(self, mask_square, top, left, height, width, mask_threshold, f_C):
        """
        Splits the droplet mask into separate droplets (8-connected regions with mask >= mask_threshold)
        and decides ZoomIn / ZoomOut for each of them.

        Droplet focal length f_D = R / (n - 1), n = 1.33 (water), with the droplet radius R approximated by
        half of the droplet's longer bounding-box side in px. The size is measured on the uncropped square
        mask, so a droplet cut by the image edge is judged by its full size. ZoomIn if f_D > f_C, i.e.
        ZoomOut if the longer side is below 2 * (1.33 - 1) * f_C = 0.66 * f_C.

        :param mask_square: Uncropped square mask from render_mask(..., return_square=True).
        :param top, left: Offset of the image crop in the square.
        :param f_C: Camera focal length in px for this image resolution.
        :return: (droplets, labels): a list of dicts (label, bbox = (row0, row1, col0, col1) with exclusive ends,
                 size_px, cut, f_D, case) for every droplet visible in the image, and the label image (height x width).
        """
        binary = (np.uint8(mask_square * 255) >= mask_threshold * 255).astype(np.uint8)
        _, labels_square, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        labels = labels_square[top:top + height, left:left + width]

        droplets = []
        for label, region in enumerate(ndimage.find_objects(labels), start=1):
            if region is None:  # droplet lies completely outside the image
                continue
            sx, sy, sw, sh = stats[label, :4]  # full extent in the square: x, y, width, height
            size_px = int(max(sw, sh))
            cut = sx < left or sy < top or sx + sw > left + width or sy + sh > top + height
            f_D = (0.5 * size_px) / (1.33 - 1)
            droplets.append({
                'label': label,
                'bbox': (region[0].start, region[0].stop, region[1].start, region[1].stop),
                'size_px': size_px,
                'cut': bool(cut),
                'f_D': f_D,
                'case': 'ZoomIn' if f_D > f_C else 'ZoomOut',
            })
        return droplets, labels
        

"""
Parameter:

WoodScape Dataset:
fd_x = 432.201
fd_y = 326.177
Mean = 379.189 approx 380

"""




















#-----------------------------------------------------------OtherPaper-----------------------------------------------------------#
"""
Raindrops on Windshield: Dataset and Lightweight Gradient-Based Detection Algorithm

Autonomous vehicles use cameras as one of the
primary sources of information about the environment. Adverse
weather conditions such as raindrops, snow, mud, and others,
can lead to various image artifacts. Such artifacts significantly
degrade the quality and reliability of the obtained visual
data and can lead to accidents if they are not detected in
time. This paper presents ongoing work on a new dataset
for training and assessing vision algorithms’ performance for
different tasks of image artifacts detection on either camera
lens or windshield. At the moment, we present a publicly
available set of images containing 8190 images, of which 3390
contain raindrops. Images are annotated with the binary mask
representing areas with raindrops. We demonstrate the appli-
cability of the dataset in the problems of raindrops presence
detection and raindrop region segmentation. To augment the
data, we also propose an algorithm for data augmentation
which allows the generation of synthetic raindrops on images.
Apart from the dataset, we present a novel gradient-based
algorithm for raindrop presence detection in a video sequence.
The experimental evaluation proves that the algorithm reliably
detects raindrops. Moreover, compared with the state-of-the-art
cross-correlation-based algorithm [1], the proposed algorithm
showed a higher quality of raindrop presence detection and
image processing speed, making it applicable for the self-check
procedure of real autonomous systems. The dataset is available
at github.com/EvoCargo/RaindropsOnW indshield.


https://arxiv.org/abs/2104.05078

https://github.com/Evocargo/RaindropsOnWindshield

"""


def op_make_bezier(xys):
    n = len(xys)
    combinations = op_pascal_row(n-1)
    def bezier(ts):
        result = []
        for t in ts:
            tpowers = (t**i for i in range(n))
            upowers = reversed([(1-t)**i for i in range(n)])
            coefs = [c*a*b for c, a, b in zip(combinations, tpowers, upowers)]
            result.append(
                tuple(sum([coef*p for coef, p in zip(coefs, ps)]) for ps in zip(*xys)))
        return result
    return bezier

def op_pascal_row(n, memo={}):
    if n in memo:
        return memo[n]
    result = [1]
    x, numerator = 1, n
    for denominator in range(1, n//2+1):
        x *= numerator
        x /= denominator
        result.append(x)
        numerator -= 1
    if n % 2 == 0:
        result.extend(reversed(result[:-1]))
    else:
        result.extend(reversed(result))
    memo[n] = result
    return result

def normalize(data):
    # Standardnormalisierung
    mean = np.mean(data)
    std_dev = np.std(data)
    standardized_data = (data - mean) / std_dev
    
    # Min-Max-Skalierung
    min_val = np.min(standardized_data)
    max_val = np.max(standardized_data)
    scaled_data = (standardized_data - min_val) / (max_val - min_val)
    
    return scaled_data

class Raindrop:
    def __init__(self, radius=50, center=(0, 0)):
        self.radius = radius
        self.center = center
    
    def generate_circle_points(self, num_points=100):
        angles = np.linspace(0, 2 * np.pi, num_points)
        x_points = self.center[0] + self.radius * np.cos(angles)
        y_points = self.center[1] + self.radius * np.sin(angles)
        return x_points, y_points
    
    def generate_ellipse_points(self, num_points=100):
        angles = np.linspace(0, 2 * np.pi, num_points)
        x_points = self.center[0] + self.radius * np.cos(angles)
        y_points = self.center[1] + 1.3 * self.radius * np.sin(angles)
        return x_points, y_points
    


    def generate_egg_shape_points(self, num_points=100, A=None, B=None, C=None, D=None, test=None):
        if A is None or B is None or C is None or D is None:
            A = (self.center[0] + 0.5 * self.radius, self.center[1] - self.radius)
            B = (self.center[0] + 0.25 * self.radius, self.center[1] + 0.5 * self.radius)
            C = (self.center[0] - 0.25 * self.radius, self.center[1] + 0.5 * self.radius)
            D = (self.center[0] - 0.5 * self.radius, self.center[1] - self.radius)
        
        ts = np.linspace(0, 1, num_points)
        
        # Erste Kurve
        xys = [A, B, C]
        bezier = op_make_bezier(xys)
        points1 = np.array(bezier(ts))
        
        # Zweite Kurve (umgekehrte Reihenfolge der Kontrollpunkte)
        xys = [C, D, A]  # Beachten Sie die umgekehrte Reihenfolge hier
        bezier = op_make_bezier(xys)
        points2 = np.array(bezier(ts))

        
        
        # Verbinden der beiden Kurven
        points = np.concatenate([points1, points2], axis=0)

                # Normalize
        points[:, 0] = normalize(np.array(points[:, 0]))
        points[:, 1] = normalize(np.array(points[:, 1]))

        ############################# TEST #############################
        # Plot
        if test:
            plt.plot(points[:, 0], points[:, 1], 'g-', label='Egg Shape (Drop)')
            plt.xlabel('x')
            plt.ylabel('y')
            plt.title('Shapes')
            plt.gca().set_aspect('equal', adjustable='box')
            plt.legend()
            plt.grid(True)
            plt.show()
        ############################# TEST #############################



        
        return points[:, 0], points[:, 1]
        
    """
    def deploy(self, raw_img=None, form_x=None, form_y=None, 
                barrel_strength_low=None, barrel_strength_high=None, 
                ib_gauss_kernel = None,
                blurr_roi_gauss_kernel=None,
                mask_blurr_gauss_kernel=None,
                brightness_factor=None,
                mood='black',
                test=False):
    """


    def op_employ(self, raw_img=None, form_x=None, form_y=None, 
                  img_gauss_kernel=None, mask_blurr_gauss_kernel=None,
                  test=None):



        # (1) Create a mask
        mask = np.zeros(raw_img.shape[:2], dtype=np.uint8)
        cv2.fillPoly(mask, [np.array(list(zip(form_x, form_y)), dtype=np.int32)], 255)

        if test:
            ############################# TEST #############################
            plt.imshow(mask)
            plt.show()
            ############################# TEST #############################


        # Blurr Image b
        image_b = raw_img.copy()

        # Apply Gaussian blur to ROI
        #if mask_blurr_gauss_kernel is None:
        #    mask_blurr_gauss_kernel = 21

        image_b = cv2.GaussianBlur(image_b, (mask_blurr_gauss_kernel, mask_blurr_gauss_kernel), 0)  # Adjust kernel size (15, 15) as needed

        if test:
            ############################# TEST #############################
            print("Blurred Image_b")
            plt.imshow(image_b)
            plt.show()
            ############################# TEST #############################





        # (2) Blurr Mask
        ## Blurr the mask and invert it
        #if img_gauss_kernel is None:
        #    img_gauss_kernel = 91


        gt_mask = mask.copy()   # Safe it for ground truth
        mask = cv2.GaussianBlur(mask, (img_gauss_kernel, img_gauss_kernel), 0)  # Adjust kernel size (15, 15) as needed



        if test:
            ############################# TEST #############################
            print("Maske")
            plt.imshow(mask)
            plt.show()
            ############################# TEST #############################



        # (3) Implementation
        # Reshape mask to have the same number of dimensions as the RGB images
        mask = mask[:, :, np.newaxis]

        # Normalize Mask from [0,255] to [0,1]
        mask = mask / np.max(mask)

        # CALC
        fused_image=(mask*image_b[:,:,:]) + ((1-mask)*raw_img[:,:,:])
        #TIMfused_image = (mask*image_b[:,:,:]) + ((1-mask)*raw_img[:,:,:])
        fused_image = fused_image.astype(np.uint8)


        if test:
            ############################# TEST #############################   
            print("End of Simulation")
            plt.imshow(fused_image)
            plt.show()
            print("Mask")
            plt.imshow(gt_mask)
            plt.show()
            ############################# TEST #############################


        return fused_image, gt_mask













