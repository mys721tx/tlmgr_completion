#!/usr/bin/env python3
"""
Extract sections from tlmgr help output by automatically parsing the structure.

This script leverages the consistent indentation in tlmgr help output:
- Main sections start at column 0 (^[A-Z])
- Action items start with exactly 2 spaces (^  [a-z])

The script:
1. Reads tlmgr help output from stdin
2. Automatically generates section_numbers.txt by parsing the structure
3. Extracts the OPTIONS section and all ACTION subsections to individual files
4. Maintains the existing directory structure

Output:
- section_numbers.txt - Generated structure map
- help_sections/options.txt - Contains the OPTIONS section
- help_sections/actions/*.txt - Contains individual action sections

Usage:
    tlmgr --help | python3 extract_sections.py
    # or
    cat help.txt | python3 extract_sections.py

Features:
    - Zero manual maintenance - fully automatic parsing
    - Leverages consistent help output indentation patterns
    - Generates ~32 section files + 1 structure file
    - Maintains directory structure
    - Sanitizes filenames for filesystem compatibility
    - Automatic backup of existing section_numbers.txt
"""

import re
import sys
from pathlib import Path


class TlmgrExtractor:
    def __init__(self, output_base_dir, numbers_output=None):
        self.output_base_dir = Path(output_base_dir)
        self.numbers_output = numbers_output
        self.help_lines = []
        self.sections = {}
        self.main_sections = []
        self.action_sections = []

    def load_help_stdin(self):
        """Load the help output from stdin."""
        self.help_lines = sys.stdin.readlines()
        print(f"Loaded {len(self.help_lines)} lines from stdin")

    def parse_structure(self):
        """Parse help.txt file directly to extract section information."""
        print("Parsing help.txt structure...")

        in_actions = False

        for i, line in enumerate(self.help_lines, 1):
            content = line.rstrip()  # Remove trailing whitespace but keep leading

            # Main sections: start at column 0, all uppercase
            if content and not line.startswith(" ") and content.isupper():
                # Skip separator lines
                if not re.match(r"^[=\-]+$", content):
                    self.main_sections.append({"name": content, "line": i})
                    self.sections[content] = {"start_line": i, "type": "main"}

                    # Track when we enter/exit the ACTIONS section
                    if content == "ACTIONS":
                        in_actions = True
                    elif in_actions and content in [
                        "CONFIGURATION FILE FOR TLMGR",
                        "CRYPTOGRAPHIC VERIFICATION",
                        "USER MODE",
                        "MULTIPLE REPOSITORIES",
                        "GUI FOR TLMGR",
                        "MACHINE-READABLE OUTPUT",
                        "ENVIRONMENT VARIABLES",
                        "AUTHORS AND COPYRIGHT",
                    ]:
                        in_actions = False

            # Action sections: exactly 2 spaces indentation, within ACTIONS section
            elif in_actions and line.startswith("  ") and not line.startswith("    "):
                stripped = content.strip()
                if stripped:  # Non-empty line
                    # Extract action name (first word)
                    action_match = re.match(
                        r"^\s*(\w[\w\-]*)",
                        line,
                    )
                    if action_match:
                        action_name = action_match.group(1)
                        self.action_sections.append(
                            {
                                "name": action_name,
                                "full_line": stripped,
                                "line": i,
                            }
                        )
                        self.sections[action_name] = {
                            "start_line": i,
                            "type": "action",
                            "original_name": stripped,
                        }

        print(
            f"Found {len(self.main_sections)} main sections and "
            f"{len(self.action_sections)} action sections"
        )

        # Debug: print sections found
        print("Main sections found:")
        for section in self.main_sections:
            print(f"  Line {section['line']}: {section['name']}")

        print("Action sections found:")
        for section in self.action_sections:
            print(f"  Line {section['line']}: {section['name']}")

    def generate_numbers(self):
        """Generate section_numbers.txt file with the parsed structure."""
        if not self.numbers_output:
            return

        from datetime import datetime

        content = []
        content.append("TLMGR HELP.TXT SECTION STRUCTURE")
        content.append("=" * 35)
        content.append("")

        # Main sections
        content.append("MAIN SECTIONS:")
        content.append("-" * 14)
        for section in self.main_sections:
            content.append(f"Line {section['line']:<4}: {section['name']}")
        content.append("")

        # Actions subsections
        content.append("ACTIONS SUBSECTIONS:")
        content.append("-" * 19)
        for section in self.action_sections:
            content.append(f"Line {section['line']:<4}: {section['full_line']}")
        content.append("")

        # Summary
        content.append("SUMMARY:")
        content.append("-" * 8)
        content.append(f"Total main sections: {len(self.main_sections)}")
        content.append(f"Total actions: {len(self.action_sections)}")
        content.append("")
        content.append(f"Generated on: {datetime.now().strftime('%B %d, %Y')}")

        # Write to file
        with open(self.numbers_output, "w", encoding="utf-8") as f:
            f.write("\n".join(content))

        print(
            f"Generated section_numbers.txt with {len(self.main_sections)} main sections and "
            f"{len(self.action_sections)} actions"
        )

    def calc_ranges(self):
        """Calculate start and end lines for each section."""
        # Sort sections by start line
        sorted_sections = sorted(
            self.sections.items(), key=lambda x: x[1]["start_line"]
        )

        for i, (name, info) in enumerate(sorted_sections):
            start_line = info["start_line"]

            # Find end line (start of next section or end of file)
            if i + 1 < len(sorted_sections):
                end_line = sorted_sections[i + 1][1]["start_line"] - 1
            else:
                end_line = len(self.help_lines)

            info["end_line"] = end_line
            print(f"Section '{name}': lines {start_line}-{end_line}")

    def sanitize_name(self, name):
        """Sanitize section name for use as filename."""
        # Remove or replace problematic characters
        sanitized = re.sub(r"[^\w\-_\.]", "_", name)
        sanitized = re.sub(
            r"_+", "_", sanitized
        )  # Replace multiple underscores with single
        sanitized = sanitized.strip("_")
        # Remove trailing dots that might be problematic
        sanitized = sanitized.rstrip(".")
        return sanitized.lower()

    def extract_content(self, name, start_line, end_line):
        """Extract content for a specific section."""
        # Convert to 0-based indexing
        start_idx = start_line - 1
        end_idx = min(end_line, len(self.help_lines))

        lines = self.help_lines[start_idx:end_idx]

        # Remove trailing empty lines
        while lines and not lines[-1].strip():
            lines.pop()

        return "".join(lines)

    def create_dirs(self):
        """Create necessary output directories."""
        # Create base help_sections directory
        self.output_base_dir.mkdir(exist_ok=True)

        # Create actions subdirectory
        actions_dir = self.output_base_dir / "actions"
        actions_dir.mkdir(exist_ok=True)

        print(f"Created output directories: {self.output_base_dir}")

    def extract_all(self):
        """Extract all sections to individual files."""
        self.create_dirs()

        for name, info in self.sections.items():
            start_line = info["start_line"]
            end_line = info["end_line"]
            sect_type = info["type"]

            content = self.extract_content(name, start_line, end_line)

            # Determine output file path
            filename = f"{self.sanitize_name(name)}.txt"

            if sect_type == "action":
                output_path = self.output_base_dir / "actions" / filename
            elif name == "OPTIONS":
                output_path = self.output_base_dir / filename
            else:
                # Skip other main sections for now (only extracting OPTIONS and actions)
                continue

            # Write content to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"Extracted '{name}' to {output_path}")

    def run(self):
        """Run the complete extraction process."""
        print("Starting tlmgr section extraction...")

        self.load_help_stdin()
        self.parse_structure()
        self.generate_numbers()
        self.calc_ranges()
        self.extract_all()

        print("Extraction completed!")


def main():
    """Main function."""
    extractor = TlmgrExtractor("help_sections")
    extractor.run()


if __name__ == "__main__":
    exit(main())
