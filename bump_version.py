import sys
from pathlib import Path

def bump_version(version_file_path=None):
    if version_file_path is None:
        version_file_path = Path(__file__).parent / "VERSION"
    else:
        version_file_path = Path(version_file_path)
    
    current_version = version_file_path.read_text().strip()
    major, minor, patch = map(int, current_version.split('.'))
    
    new_version = f"{major}.{minor}.{patch + 1}"
    version_file_path.write_text(new_version + "\n")
    
    print(f"Version bumped: {current_version} -> {new_version}")
    return new_version

if __name__ == "__main__":
    bump_version()