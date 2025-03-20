# tarc

tarc is an experimental tool for tracking datasets distributed through
BitTorrent. It scans your data and relates files to known BitTorrent
metadata.

## Quick Start

- Build the virtual environment and install tarc
  ```
  make
  ```
- Use the newly built virtual environment
  ```
  source venv/bin/activate
  ```
- Add qBittorrent client endpoint
  ```
  tarc client add -n qbit -u admin -e "https://qbit.example.org"
  ```
- Scan the endpoint
  ```
  tarc scan -n qbit -u admin -p password
  ```

## Copyright and License

Copyright (C) 2025 Kris Lamoureux

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <https://www.gnu.org/licenses/>.
