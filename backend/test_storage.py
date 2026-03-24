import asyncio
from io import BytesIO
from fastapi import UploadFile
from storage_client import upload_image
from enums import ImageType

async def test_upload():
    """Test the storage client with a simple SVG image."""

    # Create a simple SVG content
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="40" stroke="black" stroke-width="3" fill="red" />
  <text x="50" y="55" font-family="Arial" font-size="12" text-anchor="middle" fill="white">Test</text>
</svg>'''

    # Convert to bytes
    svg_bytes = svg_content.encode('utf-8')

    # Create UploadFile-like object
    class MockUploadFile:
        def __init__(self, filename, content, content_type):
            self.filename = filename
            self.content_type = content_type
            self._content = content

        async def read(self):
            return self._content

    # Create mock upload file
    mock_file = MockUploadFile(
        filename="test_image.svg",
        content=svg_bytes,
        content_type="image/svg+xml"
    )

    # Test parameters
    user_id = 123
    username = "testuser"
    image_type = ImageType.CHAT

    try:
        print("Testing storage client upload...")
        print(f"User ID: {user_id}")
        print(f"Username: {username}")
        print(f"Image Type: {image_type.value}")
        print(f"File: {mock_file.filename}")
        print(f"Content Type: {mock_file.content_type}")

        # Attempt upload
        result = await upload_image(user_id, username, image_type, mock_file)

        print("\nUpload successful!")
        print(f"URL: {result['url']}")
        print(f"Filename: {result['filename']}")

    except Exception as e:
        print(f"\nUpload failed with error: {e}")
        print("Note: This is expected if AWS credentials are not configured or invalid.")

if __name__ == "__main__":
    asyncio.run(test_upload())