// Firebase Web SDK Configuration
// Project: gg-poker-prod
//
// 이 파일은 클라이언트 사이드 Firebase 초기화용입니다.
// 서버 사이드 마이그레이션은 서비스 계정 키가 필요합니다.

import { initializeApp } from "firebase/app";
import { getAnalytics } from "firebase/analytics";
import { getFirestore } from "firebase/firestore";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyCdfbSR5OORDQ1_MhF0nRDIGpN65oUhpBM",
  authDomain: "gg-poker-prod.firebaseapp.com",
  projectId: "gg-poker-prod",
  storageBucket: "gg-poker-prod.firebasestorage.app",
  messagingSenderId: "45067711104",
  appId: "1:45067711104:web:b41501d874004b0bb1ac65",
  measurementId: "G-DQ29FFNBWQ"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
const db = getFirestore(app);
const auth = getAuth(app);

export { app, analytics, db, auth, firebaseConfig };
