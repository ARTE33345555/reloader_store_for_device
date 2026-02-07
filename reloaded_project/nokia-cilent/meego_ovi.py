import os
import time
from libusb1 import usb1
from tqdm import tqdm  # pip install tqdm

# List connected USB devices
def list_usb_devices():
    with usb1.USBContext() as context:
        print("Connected USB devices:")
        for device in context.getDeviceList(skip_on_error=True):
            print(f"Bus {device.getBusNumber():03d} Device {device.getDeviceAddress():03d} "
                  f"ID {device.getVendorID():04x}:{device.getProductID():04x}")

# Copy file with tqdm progress bar
def copy_file(src, dst):
    total_size = os.path.getsize(src)
    buffer_size = 4096

    with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst, tqdm(total=total_size, unit='B', unit_scale=True, desc="Installing") as pbar:
        while chunk := fsrc.read(buffer_size):
            fdst.write(chunk)
            pbar.update(len(chunk))
            time.sleep(0.01)  # simulate transfer speed

# Confirmation prompt (y/n)
def confirm(prompt="Are you sure? (y/n): "):
    while True:
        answer = input(prompt).strip().lower()
        if answer in ('y', 'n'):
            return answer == 'y'
        print("Please enter 'y' or 'n'.")

# Main CLI installer
def main():
    print("=== Reloaded Store Installer ===")
    
    # List USB devices
    list_usb_devices()
    
    # Ask user confirmation
    if not confirm("Do you want to continue with installation? (y/n): "):
        print("Installation cancelled.")
        return
    
    # Prepare dummy file for testing
    src_file = 'reloaded_store_client.bin'
    dst_file = 'device:/usr/local/bin/reloaded_store'
    if not os.path.exists(src_file):
        with open(src_file, 'wb') as f:
            f.write(os.urandom(1024*1024))  # 1 MB
    
    # Copy with tqdm progress
    copy_file(src_file, dst_file)
    
    print("Installation completed successfully!")

if __name__ == "__main__":
    main()
