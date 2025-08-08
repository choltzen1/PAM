# Promo App

## Overview
The Promo App is a web-based application designed to streamline the management and promotion of various products. It provides tools for uploading, editing, and validating promotional data, ensuring consistency and accuracy across different campaigns. The app is tailored for T-mobil promotions team that need to manage large-scale promotions efficiently.

### Key Features
- **Data Upload and Validation**: Upload SKU lists and trade-in files, and validate them for errors.
- **Promotion Editing**: Edit promotional details such as BPTCR, segment names, and more.
- **Responsive Design**: Optimized for both desktop and mobile devices.
- **Error Highlighting**: Highlights mismatched or invalid data for quick resolution.

## Getting Started
Follow these steps to set up and run the Promo App on your local machine.

### Prerequisites
- **Python 3.10 or higher**
- **pip** (Python package manager)
- **Virtual Environment** (optional but recommended)

### Installation
1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd promo-app
   ```

2. **Set Up a Virtual Environment** (optional):
   ```bash
   python -m venv venv
   .\venv\Scripts\activate  # On Windows
   source venv/bin/activate  # On macOS/Linux
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application
1. **Start the Development Server**:
   ```bash
   python app.py
   ```

2. **Access the Application**:
   Open your browser and navigate to `http://127.0.0.1:5000`.

### File Structure
- **`app.py`**: Main application file.
- **`templates/`**: HTML templates for the web pages.
- **`static/css/`**: CSS files for styling.
- **`data/`**: Contains JSON files and other data resources.
- **`uploads/`**: Directory for uploaded files.

### Notes
- Ensure that the `uploads/` directory has the necessary permissions for file uploads.
- Update the `promotions.json` file in the `data/` directory with your initial data if needed.

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## License
This project is licensed under a proprietary T-Mobile license. See the LICENSE file for details.

## Contact
For any inquiries or support, please contact cade.holtzen1@t-mobile.com.
