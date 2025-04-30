# Secure File Transfer with AES Encryption

A Python application for securely transferring files over LAN using AES encryption.

## Features
- Server and client components with PyQt5 GUI
- AES-256 encryption for secure file transfers
- Simple and intuitive user interface

## Setup
1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the server:
   ```
   python server.py
   ```

3. Run the client:
   ```
   python client.py
   ```

## Usage
1. Start the server and set up the port and password
2. On the client, connect to the server using its IP address, port, and the shared password
3. Select a file to transfer
4. The file will be encrypted, sent to the server, and decrypted 