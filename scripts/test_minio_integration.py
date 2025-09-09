#!/usr/bin/env python3
"""
Test script for MinIO integration
Run this to test MinIO connectivity and basic operations
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.services.minio_service import minio_service

async def test_minio_integration():
    """Test MinIO integration"""
    
    print("🧪 Testing MinIO Integration")
    print("=" * 50)
    
    # Test 1: Connection and bucket creation
    print("1️⃣ Testing MinIO connection and bucket creation...")
    try:
        bucket_created = await minio_service.ensure_bucket_exists()
        if bucket_created:
            print("✅ MinIO connection successful and bucket exists")
        else:
            print("❌ Failed to create/access bucket")
            return False
    except Exception as e:
        print(f"❌ MinIO connection failed: {e}")
        return False
    
    # Test 2: File upload
    print("\n2️⃣ Testing file upload...")
    try:
        test_data = b"Hello MinIO! This is a test file."
        test_filename = "test.txt"
        
        success, public_url = await minio_service.upload_file(
            test_data, 
            f"test/{test_filename}",
            "text/plain"
        )
        
        if success:
            print(f"✅ File uploaded successfully")
            print(f"   Public URL: {public_url}")
        else:
            print("❌ File upload failed")
            return False
    except Exception as e:
        print(f"❌ File upload error: {e}")
        return False
    
    # Test 3: File existence check
    print("\n3️⃣ Testing file existence check...")
    try:
        exists = await minio_service.file_exists(f"test/{test_filename}")
        if exists:
            print("✅ File exists check successful")
        else:
            print("❌ File not found")
            return False
    except Exception as e:
        print(f"❌ File existence check error: {e}")
        return False
    
    # Test 4: Generate presigned URL
    print("\n4️⃣ Testing presigned URL generation...")
    try:
        from datetime import timedelta
        presigned_url = await minio_service.generate_presigned_url(
            f"test/{test_filename}",
            expires=timedelta(minutes=5)
        )
        
        if presigned_url:
            print("✅ Presigned URL generated successfully")
            print(f"   URL: {presigned_url[:100]}...")
        else:
            print("❌ Failed to generate presigned URL")
            return False
    except Exception as e:
        print(f"❌ Presigned URL generation error: {e}")
        return False
    
    # Test 5: File info retrieval
    print("\n5️⃣ Testing file info retrieval...")
    try:
        file_info = await minio_service.get_file_info(f"test/{test_filename}")
        if file_info:
            print("✅ File info retrieved successfully")
            print(f"   Size: {file_info['size']} bytes")
            print(f"   Content Type: {file_info['content_type']}")
        else:
            print("❌ Failed to get file info")
            return False
    except Exception as e:
        print(f"❌ File info retrieval error: {e}")
        return False
    
    # Test 6: File deletion
    print("\n6️⃣ Testing file deletion...")
    try:
        deleted = await minio_service.delete_file(f"test/{test_filename}")
        if deleted:
            print("✅ File deleted successfully")
        else:
            print("❌ File deletion failed")
            return False
    except Exception as e:
        print(f"❌ File deletion error: {e}")
        return False
    
    # Test 7: Verify deletion
    print("\n7️⃣ Verifying file deletion...")
    try:
        exists = await minio_service.file_exists(f"test/{test_filename}")
        if not exists:
            print("✅ File deletion verified - file no longer exists")
        else:
            print("❌ File still exists after deletion")
            return False
    except Exception as e:
        print(f"❌ Deletion verification error: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All MinIO integration tests passed!")
    print("MinIO is ready for production use.")
    return True

async def test_with_real_image():
    """Test with a real image file if available"""
    print("\n📸 Testing with real image...")
    
    # Try to find test images in uploads folder
    uploads_path = Path("uploads")
    test_images = []
    
    if uploads_path.exists():
        for ext in ['*.jpg', '*.jpeg', '*.png']:
            test_images.extend(uploads_path.rglob(ext))
    
    if not test_images:
        print("⚠️  No test images found in uploads folder")
        return
    
    test_image = test_images[0]
    print(f"Using test image: {test_image}")
    
    try:
        with open(test_image, 'rb') as f:
            image_data = f.read()
        
        object_name = minio_service.generate_object_name(test_image.name, "test-images")
        success, public_url = await minio_service.upload_file(
            image_data, 
            object_name,
            f"image/{test_image.suffix.lower().lstrip('.')}"
        )
        
        if success:
            print(f"✅ Real image uploaded successfully")
            print(f"   Object: {object_name}")
            print(f"   URL: {public_url}")
            
            # Generate presigned URL
            presigned_url = await minio_service.generate_presigned_url(object_name)
            if presigned_url:
                print(f"   Presigned URL: {presigned_url[:100]}...")
            
            # Clean up
            await minio_service.delete_file(object_name)
            print("✅ Test image cleaned up")
        else:
            print("❌ Real image upload failed")
    except Exception as e:
        print(f"❌ Real image test error: {e}")

def print_config():
    """Print current MinIO configuration"""
    print("📋 Current MinIO Configuration:")
    print(f"   Endpoint: {settings.MINIO_ENDPOINT}")
    print(f"   Bucket: {settings.MINIO_BUCKET_NAME}")
    print(f"   Secure: {settings.MINIO_SECURE}")
    print(f"   Storage Type: {settings.FILE_STORAGE_TYPE}")
    print(f"   Base URL: {settings.minio_base_url}")
    print(f"   Console: http://{settings.MINIO_ENDPOINT.replace(':9000', ':9001')}")

async def main():
    """Main test function"""
    print_config()
    print()
    
    # Basic integration tests
    success = await test_minio_integration()
    
    if success:
        # Test with real image
        await test_with_real_image()
        
        print("\n🚀 MinIO integration is ready!")
        print("You can now:")
        print("   1. Run the database migration: psql -d your_db -f migration_minio_support.sql")
        print("   2. Set FILE_STORAGE_TYPE=minio in your .env file")
        print("   3. Start uploading files to MinIO!")
    else:
        print("\n❌ MinIO integration tests failed!")
        print("Please check your MinIO configuration and server status.")

if __name__ == "__main__":
    asyncio.run(main())