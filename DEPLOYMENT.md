# Railway Deployment Guide for Stark Products

## Step 1: Set up GitHub Repository

1. **Install Git** (if not already installed):
   - Download from: https://git-scm.com/download/windows
   - Or use GitHub Desktop: https://desktop.github.com/

2. **Create GitHub Repository**:
   - Go to https://github.com
   - Click "New repository"
   - Repository name: `stark-products-platform`
   - Description: "B2B bathroom accessories platform for Stark Products"
   - Set to Public (for free deployment)
   - Don't initialize with README (we already have one)

3. **Push Code to GitHub**:
   ```bash
   cd "C:\Connor.H\Dev Stuff\Stark products\backend"
   git init
   git add .
   git commit -m "Initial commit - Stark Products platform"
   git branch -M main
   git remote add origin https://github.com/yourusername/stark-products-platform.git
   git push -u origin main
   ```

## Step 2: Set up MongoDB Atlas (Production Database)

1. **Create MongoDB Atlas Account**:
   - Go to https://cloud.mongodb.com
   - Sign up for free account

2. **Create Cluster**:
   - Choose "M0 Sandbox" (free tier)
   - Select region (closest to your users)
   - Cluster name: `stark-products`

3. **Set up Database Access**:
   - Go to "Database Access"
   - Add new database user
   - Username: `starkproducts`
   - Password: Generate strong password (save it!)
   - Role: "Atlas admin" or "Read and write to any database"

4. **Configure Network Access**:
   - Go to "Network Access"
   - Add IP Address: `0.0.0.0/0` (allows access from anywhere)
   - Or add specific Railway IPs for better security

5. **Get Connection String**:
   - Go to "Clusters" → "Connect"
   - Choose "Connect your application"
   - Copy the connection string
   - Format: `mongodb+srv://starkproducts:PASSWORD@cluster0.xxxxx.mongodb.net/`

## Step 3: Deploy to Railway

1. **Create Railway Account**:
   - Go to https://railway.app
   - Sign up with GitHub account

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your `stark-products-platform` repository

3. **Configure Environment Variables**:
   In Railway dashboard, go to Variables tab and add:

   ```env
   ENVIRONMENT=production
   MONGO_URL=mongodb+srv://starkproducts:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/
   DB_NAME=stark_products_prod
   JWT_SECRET_KEY=your-super-secret-jwt-key-make-this-long-and-random
   JWT_ALGORITHM=HS256
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
   BCRYPT_ROUNDS=12
   API_PREFIX=/api
   API_VERSION=1.0.0
   DEBUG=false
   CORS_ORIGINS=https://your-project-name.railway.app
   PORT=8000
   ```

4. **Deploy**:
   - Railway will automatically build and deploy
   - Wait for deployment to complete
   - Your app will be available at: `https://your-project-name.railway.app`

## Step 4: Test Production Deployment

1. **Check Health Endpoint**:
   - Visit: `https://your-project-name.railway.app/api/health`
   - Should return: `{"status":"healthy","timestamp":"..."}`

2. **Test Website**:
   - Visit: `https://your-project-name.railway.app/`
   - Should show Stark Products homepage
   - Test products page: `https://your-project-name.railway.app/static/products.html`

3. **Add Sample Products**:
   - Create a simple script to add products to production DB
   - Or use Railway's built-in terminal

## Step 5: Custom Domain (Optional)

1. **In Railway Dashboard**:
   - Go to Settings → Domains
   - Add custom domain: `demo.starkproducts.co.za`
   - Update DNS records as instructed

2. **Update CORS Settings**:
   - Add your custom domain to `CORS_ORIGINS` environment variable

## Step 6: Monitoring and Logs

1. **View Logs**:
   - Railway Dashboard → Deployments → View Logs
   - Monitor for any errors or issues

2. **Set up Monitoring**:
   - Railway provides basic metrics
   - Consider adding error tracking (Sentry, etc.)

## Troubleshooting

**Common Issues:**

1. **Build Fails**:
   - Check `requirements.txt` for correct dependencies
   - Ensure Python version compatibility

2. **Database Connection Error**:
   - Verify MongoDB Atlas connection string
   - Check network access settings
   - Ensure database user has correct permissions

3. **Static Files Not Loading**:
   - Verify `static` directory is in repository
   - Check `StaticFiles` mount in `server.py`

4. **Environment Variables**:
   - Double-check all required variables are set
   - No spaces around `=` in variable definitions

## Production Checklist

- [ ] MongoDB Atlas cluster created and configured
- [ ] Database user created with proper permissions
- [ ] Network access configured
- [ ] GitHub repository created and code pushed
- [ ] Railway project created and connected to GitHub
- [ ] All environment variables configured
- [ ] Production deployment successful
- [ ] Health check endpoint responding
- [ ] Website loading correctly
- [ ] Products displaying with images
- [ ] Quote requests working
- [ ] Custom domain configured (optional)

## Support

If you encounter any issues:
1. Check Railway deployment logs
2. Verify MongoDB Atlas connection
3. Test API endpoints individually
4. Check browser console for JavaScript errors

**Estimated Total Time**: 30-45 minutes
**Cost**: Free (using free tiers of Railway and MongoDB Atlas)
