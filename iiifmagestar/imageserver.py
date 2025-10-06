from typing import Optional, Tuple, List
from pathlib import Path
import cv2
import numpy as np


class IIIFImageServer:
    def __init__(self, image_dir: str):
        self.image_dir = Path(image_dir)

    def find_image_file(self, identifier: str) -> Optional[Path]:
        """Find the image file for the given identifier."""
        path_delimiters = ['..', '/', '\\']
        if any([delimiter in identifier for delimiter in path_delimiters]):
            return None
        accepted_formats = ('.jpg', '.jpeg', '.png', '.tiff', '.tif', '.webp', '.jp2', '.pdf')
        # I want to specify a particular format
        if identifier.endswith(accepted_formats):
            file_path = self.image_dir /identifier
            if file_path.exists():
                return file_path
        # I want to choose the first available format from the list
        for ext in accepted_formats:
            file_path = self.image_dir / f"{identifier}{ext}"
            if file_path.exists():
                return file_path
        return None

    def parse_region(self, region: str, img_width: int, img_height: int) -> Tuple[int, int, int, int]:
        """Parse IIIF region parameter and return (x, y, width, height)."""
        if region == "full":
            return 0, 0, img_width, img_height

        # Handle square region (new in 3.0)
        if region == "square":
            if img_width == img_height:
                return 0, 0, img_width, img_height
            elif img_width > img_height:
                # Landscape: center horizontally
                x = (img_width - img_height) // 2
                return x, 0, img_height, img_height
            else:
                # Portrait: center vertically
                y = (img_height - img_width) // 2
                return 0, y, img_width, img_width

        # Handle percentage regions
        if region.startswith("pct:"):
            pct_values = region[4:].split(',')
            if len(pct_values) == 4:
                x_pct, y_pct, w_pct, h_pct = map(float, pct_values)
                x = int(img_width * x_pct / 100)
                y = int(img_height * y_pct / 100)
                w = int(img_width * w_pct / 100)
                h = int(img_height * h_pct / 100)
                return x, y, w, h

        # Handle absolute pixel regions
        values = region.split(',')
        if len(values) == 4:
            x, y, w, h = map(int, values)
            # Ensure region is within image bounds
            x = max(0, min(x, img_width))
            y = max(0, min(y, img_height))
            w = min(w, img_width - x)
            h = min(h, img_height - y)
            return x, y, w, h

        # Default to full image
        return 0, 0, img_width, img_height

    def parse_size(self, size: str, region_width: int, region_height: int) -> Tuple[int, int]:
        """Parse IIIF size parameter and return (width, height)."""
        if size == "max":
            return region_width, region_height

        # Handle ^max (upscaling allowed) - new in 3.0
        if size.startswith("^"):
            # For this implementation, treat same as without ^
            return self.parse_size(size[1:], region_width, region_height)

        # Handle percentage scaling
        if size.startswith("pct:"):
            pct = float(size[4:])
            w = int(region_width * pct / 100)
            h = int(region_height * pct / 100)
            return max(1, w), max(1, h)

        # Handle specific width/height combinations
        if ',' in size:
            w_str, h_str = size.split(',')

            # Width specified, height auto
            if w_str and not h_str:
                w = int(w_str)
                h = int(region_height * w / region_width)
                return w, max(1, h)

            # Height specified, width auto
            if h_str and not w_str:
                h = int(h_str)
                w = int(region_width * h / region_height)
                return max(1, w), h

            # Both specified (exact size)
            if w_str and h_str:
                return int(w_str), int(h_str)

        # Handle !w,h (best fit) - new in 3.0
        if size.startswith("!"):
            size = size[1:]
            if ',' in size:
                max_w, max_h = map(int, size.split(','))
                # Calculate best fit
                scale_w = max_w / region_width
                scale_h = max_h / region_height
                scale = min(scale_w, scale_h)
                w = int(region_width * scale)
                h = int(region_height * scale)
                return max(1, w), max(1, h)

        # Just a number means width, height auto
        if size.isdigit():
            w = int(size)
            h = int(region_height * w / region_width)
            return w, max(1, h)

        # Default to original size
        return region_width, region_height

    def apply_rotation(self, image: np.ndarray, rotation: str) -> np.ndarray:
        """Apply rotation to the image."""
        if rotation == "0":
            return image

        # Handle mirroring (indicated by !)
        mirror = rotation.startswith("!")
        if mirror:
            rotation = rotation[1:]
            image = cv2.flip(image, 1)  # Horizontal flip

        # Apply rotation
        try:
            angle = float(rotation)
            if angle != 0:
                # Handle arbitrary rotation (new in 3.0)
                if angle % 90 == 0:
                    # Use fast rotation for 90-degree increments
                    angle = angle % 360
                    if angle == 90:
                        image = cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
                    elif angle == 180:
                        image = cv2.rotate(image, cv2.ROTATE_180)
                    elif angle == 270:
                        image = cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
                else:
                    # Arbitrary angle rotation
                    height, width = image.shape[:2]
                    center = (width // 2, height // 2)
                    rotation_matrix = cv2.getRotationMatrix2D(center, -angle, 1.0)

                    # Calculate new dimensions to fit rotated image
                    cos_angle = abs(rotation_matrix[0, 0])
                    sin_angle = abs(rotation_matrix[0, 1])
                    new_width = int((height * sin_angle) + (width * cos_angle))
                    new_height = int((height * cos_angle) + (width * sin_angle))

                    # Adjust translation
                    rotation_matrix[0, 2] += (new_width / 2) - center[0]
                    rotation_matrix[1, 2] += (new_height / 2) - center[1]

                    image = cv2.warpAffine(image, rotation_matrix, (new_width, new_height),
                                         flags=cv2.INTER_LANCZOS4,
                                         borderMode=cv2.BORDER_CONSTANT,
                                         borderValue=(255, 255, 255))
        except ValueError:
            # Invalid rotation value, return original
            pass

        return image

    def encode_image(self, image: np.ndarray, format: str, quality: str = "default") -> bytes:
        """Encode image to specified format."""
        # Handle quality parameter
        encode_params = []

        # Convert quality to proper format
        if quality == "color" or quality == "default":
            pass  # Keep as is
        elif quality == "gray":
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        elif quality == "bitonal":
            if len(image.shape) == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, image = cv2.threshold(image, 128, 255, cv2.THRESH_BINARY)

        # Encode based on format
        format_lower = format.lower()
        if format_lower in ["jpg", "jpeg"]:
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, 90]
            success, buffer = cv2.imencode('.jpg', image, encode_params)
        elif format_lower == "png":
            encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 6]
            success, buffer = cv2.imencode('.png', image, encode_params)
        elif format_lower == "webp":
            encode_params = [cv2.IMWRITE_WEBP_QUALITY, 90]
            success, buffer = cv2.imencode('.webp', image, encode_params)
        elif format_lower == "tif" or format_lower == "tiff":
            success, buffer = cv2.imencode('.tiff', image)
        else:
            # Default to JPEG
            success, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])

        if not success:
            raise ValueError(f"Failed to encode image as {format}")

        return buffer.tobytes()
