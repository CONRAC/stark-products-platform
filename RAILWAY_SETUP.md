# Railway Environment Variables Setup

## Required Environment Variables

Copy and paste these into your Railway dashboard under Variables tab:

### 1. MongoDB Connection
```
MONGO_URL=mongodb+srv://<db_username>:<db_password>@stark-products.chrzjhc.mongodb.net/?retryWrites=true&w=majority&appName=stark-products
```
**IMPORTANT**: Replace `<db_username>` and `<db_password>` with your actual MongoDB Atlas credentials.

### 2. Security & App Config
```
JWT_SECRET=stark-products-super-secure-jwt-secret-key-2025-production-ready
ENVIRONMENT=production
DEBUG=false
API_PREFIX=/api
```

### 3. CORS Configuration  
```
CORS_ORIGINS=https://your-app-name.up.railway.app
```
**NOTE**: Replace `your-app-name` with your actual Railway app URL once deployed.

## Steps to Deploy:

1. **Upload updated server.py to GitHub** (the one with resilient MongoDB connection)
2. **Go to Railway Dashboard** → Your Project → Variables tab
3. **Add all the environment variables above**
4. **Click "Deploy" to redeploy**
5. **Check the logs** for successful startup

## Health Check URLs:
- Simple: `https://your-app.up.railway.app/health`  
- Detailed: `https://your-app.up.railway.app/api/health`

## Expected Success:
✅ Build completes successfully
✅ Health check passes  
✅ App shows "Deployment successful"
✅ API endpoints accessible

---

**Next Steps After Deployment:**
1. Test the health endpoints
2. Set up your MongoDB Atlas database with sample data
3. Update the frontend to point to your Railway backend URL
