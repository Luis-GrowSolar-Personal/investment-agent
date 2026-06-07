require('dotenv').config({ path: require('path').resolve(__dirname, '../.env') });

const path = require('path');
const fs = require('fs');
const express = require('express');
const cors = require('cors');
const { clerkMiddleware } = require('@clerk/express');
const evaluateRouter  = require('./routes/evaluate');
const saveRouter      = require('./routes/save');
const radarRouter     = require('./routes/radar');
const portfolioRouter = require('./routes/portfolio');
const usersRouter      = require('./routes/users');
const dashboardRouter  = require('./routes/dashboard');
const movesRouter             = require('./routes/moves');
const ownerTickerConfigRouter = require('./routes/ownerTickerConfig');

const app = express();
// Railway sets PORT dynamically; default to 3001 for local dev.
const PORT = process.env.PORT || 3001;
const isProd = process.env.NODE_ENV === 'production';

// In dev, the client runs on Vite at :5173 and makes cross-origin fetches to
// the API on :3001. In production, the server static-serves the client build,
// so the requests are same-origin and CORS is unnecessary.
if (!isProd) {
  app.use(cors({ origin: 'http://localhost:5173' }));
}

app.use(express.json({ limit: '10mb' }));
app.use(clerkMiddleware());

app.use('/api/evaluate', evaluateRouter);
app.use('/api/save', saveRouter);
app.use('/api/radar', radarRouter);
app.use('/api/portfolio', portfolioRouter);
app.use('/api/users',     usersRouter);
app.use('/api/dashboard', dashboardRouter);
app.use('/api/moves',              movesRouter);
app.use('/api/owner-ticker-config', ownerTickerConfigRouter);

// Production: serve the Vite build at /. The build step (defined in
// nixpacks.toml at repo root) runs `npm run build` in client/, which writes
// the SPA bundle to client/dist. Any non-/api request falls through to
// index.html so React Router can handle client-side routing.
const clientDistPath = path.resolve(__dirname, '..', 'client', 'dist');
if (isProd && fs.existsSync(clientDistPath)) {
  app.use(express.static(clientDistPath));
  app.get(/^(?!\/api\/).*/, (req, res) => {
    res.sendFile(path.join(clientDistPath, 'index.html'));
  });
  console.log(`Serving SPA from ${clientDistPath}`);
}

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT} (NODE_ENV=${process.env.NODE_ENV || 'development'})`);
});
