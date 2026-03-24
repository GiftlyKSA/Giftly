import asyncio
from io import BytesIO
from fastapi import UploadFile
from storage_client import upload_media

async def test_message_media_upload():
    """Test message media upload functionality."""

    # Create a simple test image (small PNG)
    png_content = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01]\xdbF\x0e\x00\x00\x00\x00IEND\xaeB`\x82'

    # Create a simple test video (very small MP4 - this is just for testing structure)
    # Note: This is not a real video file, just testing the upload mechanism
    mp4_content = b'\x00\x00\x00\x20ftypmp41\x00\x00\x00\x00mp41mp42isom\x00\x00\x00(moov\x00\x00\x00\x1cmvhd\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\xe8\x00\x00\x00\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01trak'

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
    image_file = MockUploadFile(
        filename="test_message_image.png",
        content=png_content,
        content_type="image/png"
    )

    video_file = MockUploadFile(
        filename="test_message_video.mp4",
        content=mp4_content,
        content_type="video/mp4"
    )

    print("Testing message media upload functionality...")
    print(f"Image file: {image_file.filename} ({image_file.size} bytes, {image_file.content_type})")
    print(f"Video file: {video_file.filename} ({video_file.size} bytes, {video_file.content_type})")

    # Test parameters
    user_id = 123
    username = "testuser"

    # Test uploading image for message
    print("\n1. Testing image upload for messages...")
    try:
        image_result = await upload_media(
            user_id=user_id,
            username=username,
            media_type="image",
            media=image_file
        )
        print("✓ Image uploaded successfully")
        print(f"  URL: {image_result['url']}")
        print(f"  Filename: {image_result['filename']}")

        # Verify folder structure
        if f"{username}/chat_images/" not in image_result['url']:
            print("✗ Image URL structure incorrect")
            return False
        else:
            print("✓ Image URL structure correct")

    except Exception as e:
        print(f"✗ Failed to upload image: {e}")
        return False

    # Test uploading video for message
    print("\n2. Testing video upload for messages...")
    try:
        video_result = await upload_media(
            user_id=user_id,
            username=username,
            media_type="video",
            media=video_file
        )
        print("✓ Video uploaded successfully")
        print(f"  URL: {video_result['url']}")
        print(f"  Filename: {video_result['filename']}")

        # Verify folder structure
        if f"{username}/chat_videos/" not in video_result['url']:
            print("✗ Video URL structure incorrect")
            return False
        else:
            print("✓ Video URL structure correct")

    except Exception as e:
        print(f"✗ Failed to upload video: {e}")
        return False

    print("\n✓ All message media uploads successful!")
    print("✓ Folder structures verified:")
    print("  - Images: {username}/chat_images/")
    print("  - Videos: {username}/chat_videos/")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_message_media_upload())
    if success:
        print("\n🎉 Message media upload test PASSED!")
    else:
        print("\n❌ Message media upload test FAILED!")