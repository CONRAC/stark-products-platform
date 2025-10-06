# Stark Products - B2B Bathroom Accessories Platform

A professional B2B e-commerce platform for Stark Products, specializing in premium bathroom accessories and fittings.

## Features

🏢 **B2B Focused**
- Company account management
- Multi-user access per company
- Professional quote generation
- Bulk ordering capabilities

🛍️ **Product Management**
- Live stock tracking
- Real-time inventory updates
- Advanced product filtering
- Professional product catalogs

📋 **Quote System**
- Interactive quote requests
- PDF quote generation
- Quote history and tracking
- Email notifications

🔒 **Security & Authentication**
- JWT-based authentication
- Role-based access control
- Secure password hashing
- Company-level permissions

## Technology Stack

- **Backend**: FastAPI + Python
- **Database**: MongoDB
- **Frontend**: HTML5 + JavaScript + Tailwind CSS
- **Authentication**: JWT + bcrypt
- **Deployment**: Railway

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run the server:
```bash
python start_server.py
```

4. Visit: `http://localhost:8001`

## API Documentation

When running locally, visit:
- API Docs: `http://localhost:8001/docs`
- Health Check: `http://localhost:8001/api/health`

## Deployment

This project is configured for Railway deployment:

1. Push to GitHub
2. Connect Railway to your repository
3. Set environment variables
4. Deploy!

## Environment Variables

Required environment variables for production:

```env
ENVIRONMENT=production
MONGO_URL=mongodb+srv://...
DB_NAME=stark_products_prod
JWT_SECRET_KEY=your-secret-key
CORS_ORIGINS=https://yourdomain.railway.app
```


