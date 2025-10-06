import os
from pathlib import Path
from typing import Optional, Tuple, List
import cv2
from starlette.applications import Starlette
from starlette.responses import Response, JSONResponse, FileResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates
import uvicorn
from .imageserver import IIIFImageServer
import asyncio

# Configuration from environment variables
IMAGE_DIR = os.environ.get('IIIF_IMAGE_DIR', '/testimages/')
BASE_URL = os.environ.get('IIIF_BASE_URL', 'http://localhost:8000')

# Template setup
TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Global server instance
server = IIIFImageServer(IMAGE_DIR)

async def get_info(request):
    """Return IIIF Image Information (3.0 format)."""
    identifier = request.path_params['identifier']

    # Find the image file
    image_path = server.find_image_file(identifier)
    if not image_path:
        return JSONResponse({"type": "BadRequest", "message": "Image not found"}, status_code=404)

    # Read image to get dimensions using asyncio
    image = await asyncio.to_thread(cv2.imread,str(image_path))
    if image is None:
        return JSONResponse({"type": "BadRequest", "message": "Invalid image file"}, status_code=400)

    height, width = image.shape[:2]

    # Build IIIF Image Information response (3.0 format)
    info = {
        "@context": "http://iiif.io/api/image/3/context.json",
        "id": f"{BASE_URL}/iiif/3/{identifier}",
        "type": "ImageService3",
        "protocol": "http://iiif.io/api/image",
        "profile": "level2",
        "width": width,
        "height": height,
        "maxArea": width * height,
        "maxHeight": height,
        "maxWidth": width,
        "preferredFormats": ["jpg", "png", "webp"],
        "extraFormats": ["tif"],
        "extraQualities": ["color", "gray", "bitonal"],
        "extraFeatures": [
            "arbitraryRotation",
            "mirroring",
            "regionSquare",
            "sizeUpscaling",
            "cors"
        ],
        "rights": "http://creativecommons.org/licenses/by/4.0/",
        "partOf": [
            {
                "id": f"{BASE_URL}/collection",
                "type": "Collection"
            }
        ]
    }

    return JSONResponse(info)

async def get_image(request):
    """Process and return IIIF image (3.0 format)."""
    identifier = request.path_params['identifier']
    region = request.path_params['region']
    size = request.path_params['size']
    rotation = request.path_params['rotation']
    quality = request.path_params['quality']
    format = request.path_params['format']

    # Find the image file
    image_path = server.find_image_file(identifier)
    if not image_path:
        return JSONResponse({"type": "BadRequest", "message": "Image not found"}, status_code=404)

    try:
        # Load the image
        image = await asyncio.to_thread(cv2.imread,str(image_path))
        if image is None:
            return JSONResponse({"type": "BadRequest", "message": "Invalid image file"}, status_code=400)

        original_height, original_width = image.shape[:2]

        # Apply region cropping
        x, y, w, h = server.parse_region(region, original_width, original_height)
        if w > 0 and h > 0:
            image = image[y:y+h, x:x+w]

        # Apply size scaling
        current_height, current_width = image.shape[:2]
        new_width, new_height = server.parse_size(size, current_width, current_height)
        if new_width != current_width or new_height != current_height:
            image = await asyncio.to_thread(cv2.resize,image, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)

        # Apply rotation (including arbitrary angles in 3.0)
        image = await asyncio.to_thread(server.apply_rotation,image, rotation)

        # Encode image
        image_bytes = await asyncio.to_thread(server.encode_image,image, format, quality)

        # Determine content type
        content_type_map = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'webp': 'image/webp',
            'tif': 'image/tiff',
            'tiff': 'image/tiff'
        }
        content_type = content_type_map.get(format.lower(), 'image/jpeg')

        return Response(
            image_bytes,
            media_type=content_type,
            headers={
                'Cache-Control': 'public, max-age=31536000',  # Cache for 1 year
                'Access-Control-Allow-Origin': '*',
                'Link': f'<{BASE_URL}/iiif/3/{identifier}/info.json>;rel="profile";type="application/ld+json"'
            }
        )

    except Exception as e:
        return JSONResponse(
            {"type": "InternalServerError", "message": f"Error processing image: {str(e)}"},
            status_code=500
        )

async def homepage(request):
    """Simple homepage with API documentation for IIIF 3.0."""
    # List available images
    image_dir = Path(IMAGE_DIR)
    images = []
    for ext in ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.webp', '.jp2', '.pdf']:
        images.extend([f.stem for f in image_dir.glob(f'*{ext}')])
    
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "base_url": BASE_URL,
            "image_dir": IMAGE_DIR,
            "images": sorted(set(images))[:10]  # Show first 10 images
        }
    )

# Define routes for IIIF 3.0
routes = [
    Route('/', homepage),
    Route('/iiif/3/{identifier}/info.json', get_info),
    Route('/iiif/3/{identifier}/{region}/{size}/{rotation}/{quality}.{format}', get_image),
    # Backward compatibility with 2.1
    Route('/iiif/2/{identifier}/info.json', get_info),
    Route('/iiif/2/{identifier}/{region}/{size}/{rotation}/{quality}.{format}', get_image),
]

# Create application with CORS middleware
middleware = [
    Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['GET'], allow_headers=['*'])
]

app = Starlette(debug=True, routes=routes, middleware=middleware)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
