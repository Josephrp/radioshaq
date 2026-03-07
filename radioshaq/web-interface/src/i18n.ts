import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en.json';
import fr from './locales/fr.json';
import es from './locales/es.json';

export const SUPPORTED_LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'fr', label: 'Français' },
  { code: 'es', label: 'Español' },
] as const;

export type SupportedLanguageCode = (typeof SUPPORTED_LANGUAGES)[number]['code'];

const STORAGE_KEY = 'radioshaq_ui_lang';

i18n.use(initReactI18next).init({
  resources: { en: { translation: en }, fr: { translation: fr }, es: { translation: es } },
  lng: (() => {
    const codes = SUPPORTED_LANGUAGES.map((l) => l.code) as string[];
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && codes.includes(stored)) return stored;
    const browser = navigator.language.split('-')[0];
    return codes.includes(browser) ? browser : 'en';
  })(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

i18n.on('languageChanged', (lng) => {
  window.localStorage.setItem(STORAGE_KEY, lng);
});

export default i18n;
