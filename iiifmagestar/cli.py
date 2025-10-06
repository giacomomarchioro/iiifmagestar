import argparse
import sys
import os
from pathlib import Path
import uvicorn


def main():
    """CLI entry point for IIIF Image Server."""
    parser = argparse.ArgumentParser(
        description='IIIF Image Server - A simple IIIF 3.0 compliant image server',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  iiifmagestar -d /path/to/images
  iiifmagestar -p 8080 -d /srv/images/ --debug
  iiifmagestar -d ./images --host 0.0.0.0 -p 8000
        """
    )

    parser.add_argument(
        '-d', '--directory',
        type=str,
        required=True,
        help='Directory containing the images to serve'
    )

    parser.add_argument(
        '-p', '--port',
        type=int,
        default=8000,
        help='Port to run the server on (default: 8000)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host to bind the server to (default: 0.0.0.0)'
    )

    parser.add_argument(
        '-u', '--url',
        type=str,
        default=None,
        help='Base URL for the server (default: http://localhost:PORT)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode'
    )

    parser.add_argument(
        '--reload',
        action='store_true',
        help='Enable auto-reload on code changes'
    )

    args = parser.parse_args()

    # Validate image directory
    image_dir = Path(args.directory).resolve()
    if not image_dir.exists():
        print(f"Error: Directory '{args.directory}' does not exist", file=sys.stderr)
        sys.exit(1)

    if not image_dir.is_dir():
        print(f"Error: '{args.directory}' is not a directory", file=sys.stderr)
        sys.exit(1)

    # Set environment variables for the application
    os.environ['IIIF_IMAGE_DIR'] = str(image_dir)

    # Set base URL
    if args.url:
        base_url = args.url.rstrip('/')
    else:
        base_url = f"http://localhost:{args.port}"
    os.environ['IIIF_BASE_URL'] = base_url

    # Print startup information
    print("=" * 60)
    print("IIIF Image Server")
    print("=" * 60)
    print(f"Image directory: {image_dir}")
    print(f"Server URL:      {base_url}")
    print(f"Host:            {args.host}")
    print(f"Port:            {args.port}")
    print(f"Debug mode:      {args.debug}")
    print("=" * 60)
    print(f"\nAccess the server at: {base_url}")
    print(f"API endpoint: {base_url}/iiif/3/{{identifier}}/info.json")
    print("\nPress CTRL+C to stop the server\n")

    # Import the app after setting environment variables
    try:
        from iiifmagestar.main import app
    except ImportError:
        print("Error: Could not import the application. Make sure the package is installed.", file=sys.stderr)
        sys.exit(1)

    # Run the server
    try:
        uvicorn.run(
            "iiifmagestar.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="debug" if args.debug else "info",
            access_log=args.debug
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        sys.exit(0)


if __name__ == '__main__':
    main()
