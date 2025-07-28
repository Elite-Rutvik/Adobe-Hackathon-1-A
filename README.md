# PDF Outline Extractor

This project extracts outlines and headings from PDF documents using PyMuPDF and outputs structured JSON files.

## Docker Setup

### Building the Docker Image

**For PowerShell (Windows):**

```powershell
docker build --platform linux/amd64 -t mysolutionname:somerandomidentifier .
```

**For Bash/Zsh (Linux/Mac):**

```bash
docker build --platform linux/amd64 -t mysolutionname:somerandomidentifier .
```

### Running the Container

**For PowerShell (Windows):**

```powershell
docker run --rm -v "${PWD}/input:/app/input" -v "${PWD}/output:/app/output" --network none mysolutionname:somerandomidentifier
```

**For Bash/Zsh (Linux/Mac):**

```bash
docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none mysolutionname:somerandomidentifier
```

## Directory Structure

The project expects the following structure:

```
project/
├── Dockerfile
├── requirements.txt
├── pdf_outline_extractor.py
├── input/          # Place your PDF files here
│   ├── document1.pdf
│   ├── document2.pdf
│   └── ...
└── output/         # JSON files will be generated here
    ├── document1.json
    ├── document2.json
    └── ...
```

## Usage

1. Create `input` and `output` directories in your project folder
2. Place PDF files in the `input` directory
3. Build the Docker image using the build command above
4. Run the container using the run command above
5. Check the `output` directory for generated JSON files

## Output Format

Each PDF generates a JSON file with the following structure:

```json
{
  "title": "Document Title",
  "outline": [
    {
      "text": "Heading Text",
      "level": "H1",
      "page": 1
    }
  ]
}
```

## Features

- Intelligent heading detection with document-type awareness
- Support for RFP, form, and flyer document types
- Enhanced line reconstruction for better text extraction
- Duplicate heading removal
- Header/footer filtering
