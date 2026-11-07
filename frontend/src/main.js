import './styles.css';
import { createApi } from './api.js';
import { mountApp } from './app.js';

const api = createApi({ mode: import.meta.env.VITE_API_MODE ?? 'mock' });
mountApp(document.getElementById('cqa-app'), api);
