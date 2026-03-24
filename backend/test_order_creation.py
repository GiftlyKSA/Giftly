import asyncio
from io import BytesIO
from fastapi import UploadFile
from storage_client import upload_image
from enums import ImageType

async def test_order_creation_with_images():
    """Test order creation with image uploads using the storage client."""

    # Create a simple test image (small PNG)
    # This is a minimal 1x1 pixel PNG in base64, but we'll create it as bytes
    png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01]\xdbF\x0e\x00\x00\x00\x00IEND\xaeB`\x82'

    # Create UploadFile-like objects
    class MockUploadFile:
        def __init__(self, filename, content, content_type):
            self.filename = filename
            self.content_type = content_type
            self.size = len(content)
            self._content = content

        async def read(self):
            return self._content

    # Create mock upload files
    image1 = MockUploadFile(
        filename="test_image1.png",
        content=png_content,
        content_type="image/png"
    )

    image2 = MockUploadFile(
        filename="test_image2.jpg",
        content=png_content,  # Using same content for simplicity
        content_type="image/jpeg"
    )

    print("Testing order creation with image uploads...")
    print(f"Image 1: {image1.filename} ({image1.size} bytes, {image1.content_type})")
    print(f"Image 2: {image2.filename} ({image2.size} bytes, {image2.content_type})")

    # Test parameters
    user_id = 123
    username = "testuser"

    # Test uploading images using storage client
    uploaded_urls = {}

    for i, img in enumerate([image1, image2], 1):
        try:
            print(f"\nUploading image {i}...")
            result = await upload_image(
                user_id=user_id,
                username=username,
                image_type=ImageType.ORDER,
                image=img
            )
            uploaded_urls[f"image{i}_url"] = result["url"]
            print(f"✓ Image {i} uploaded successfully")
            print(f"  URL: {result['url']}")
            print(f"  Filename: {result['filename']}")

        except Exception as e:
            print(f"✗ Failed to upload image {i}: {e}")
            return False

    print("\n✓ All images uploaded successfully!")
    print(f"✓ Total images uploaded: {len(uploaded_urls)}")
    print("✓ URLs generated:")
    for key, url in uploaded_urls.items():
        print(f"  {key}: {url}")

    # Verify folder structure in URLs
    for url in uploaded_urls.values():
        if f"{username}/order_creation_images/" not in url:
            print(f"✗ URL structure incorrect: {url}")
            return False

    print("✓ URL structure verification passed")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_order_creation_with_images())
    if success:
        print("\n🎉 Order creation with image uploads test PASSED!")
    else:
        print("\n❌ Order creation with image uploads test FAILED!")