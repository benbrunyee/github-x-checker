# GitHub X.com Profile Checker

This script automates the process of searching GitHub repositories and checking if their owners have deactivated X.com (formerly Twitter) profiles.

## Features

- Search GitHub repositories based on user input
- Sort repositories by least recent activity
- Check repository owners' profiles for X.com/Twitter links
- Automatically detect deactivated X.com profiles
- Log deactivated profiles to a file

## Setup

1. Install Python 3.7 or higher
2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Run the script:

   ```bash
   python github_x_checker.py
   ```

2. Enter your search query when prompted
3. The script will:
   - Open GitHub and search for repositories
   - Visit each repository owner's profile
   - Check for X.com/Twitter links
   - Verify if the X.com profiles are deactivated
   - Log deactivated profiles to `deactivated_users.log`

## Logs

Deactivated X.com profiles are logged to `deactivated_users.log` with the following information:

- GitHub profile URL
- X.com profile URL

The log file rotates when it reaches 10MB to manage disk space.
