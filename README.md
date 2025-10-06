 # iiifmagestar 🇮🇮🇮🇫🧙✨

This IIIF (2.0,3.0) Image Server is build for didactic and research purposes, with in mind simplicity, fast-deployment and multi-format capabilities. It depends on [OpenCV](https://opencv.org/) for processing the and [Starlette](https://www.starlette.dev/) for serving the images.

## Installation

### Development version

```
pip install git+https://github.com/giacomomarchioro/iiifmagestar.git
```

## Usage

To serve images in `/path/to/images` directory:

```
iiifmagestar -d /path/to/images
```

The server will be accessible at `localhost:8000`.

```
usage: iiifmagestar [-h] -d DIRECTORY [-p PORT] [--host HOST] [-u URL] [--debug] [--reload]

IIIF Image Server - A simple IIIF 3.0 compliant image server

options:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Directory containing the images to serve
  -p PORT, --port PORT  Port to run the server on (default: 8000)
  --host HOST           Host to bind the server to (default: 0.0.0.0)
  -u URL, --url URL     Base URL for the server (default: http://localhost:PORT)
  --debug               Run in debug mode
  --reload              Enable auto-reload on code changes

Examples:
  iiifmagestar -d /path/to/images
  iiifmagestar -p 8080 -d /srv/images/ --debug
  iiifmagestar -d ./images --host 0.0.0.0 -p 8000
```