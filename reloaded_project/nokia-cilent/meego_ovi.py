import os
import time
from libusb1 import usb1

# Simple CLI progress bar
def progress_bar(current, total, bar_length=30):
    fraction = current / total
    arrow = '#' * int(fraction * bar_length)
    padding = '-' * (bar_length - len(arrow))
    end_char = '\r' if current < total else '\n'
    print(f'Progress: [{arrow}{padding}] {int(fraction*100)}%', end=end_char)

# List connected USB devices
def list_usb_devices():
    with usb1.USBContext() as context:
        print("Connected USB devices:")
        for device in context.getDeviceList(skip_on_error=True):
            print(f"Bus {device.getBusNumber():03d} Device {device.getDeviceAddress():03d} "
                  f"ID {device.getVendorID():04x}:{device.getProductID():04x}")

# Copy file with CLI progress bar
def copy_file(src, dst):
    total_size = os.path.getsize(src)
    copied = 0
    buffer_size = 4096

    with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
        while chunk := fsrc.read(buffer_size):
            fdst.write(chunk)
            copied += len(chunk)
            progress_bar(copied, total_size)
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
    
    print("Installing Reloaded Store...")
    copy_file(src_file, dst_file)
    
    print("Installation completed successfully!")

if __name__ == "__main__":
    main()
