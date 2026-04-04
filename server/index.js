require('dotenv').config({ path: require('path').resolve(__dirname, '../.env') });

const express = require('express');
const cors = require('cors');
const { clerkMiddleware } = require('@clerk/express');
const evaluateRouter = require('./routes/evaluate');

const app = express();
const PORT = 3001;

app.use(cors({ origin: 'http://localhost:5173' }));
app.use(express.json({ limit: '2mb' }));
app.use(clerkMiddleware());

app.use('/api/evaluate', evaluateRouter);

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
