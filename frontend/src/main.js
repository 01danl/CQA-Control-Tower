import './styles.css';
import { createApi } from './api.js';
import { mountApp } from './app.js';

const api = createApi({ mode: import.meta.env.VITE_API_MODE ?? 'mock', baseUrl: import.meta.env.VITE_API_BASE_URL ?? '/api/v1' });
mountApp(document.getElementById('cqa-app'), api);
