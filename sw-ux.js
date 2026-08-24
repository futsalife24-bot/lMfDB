// 旧改善版URLは /ux/ へ移行。誤ってルート全体を制御していた登録を安全に解除する。
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>{event.waitUntil((async()=>{await caches.delete('lmfdb-ux-preview-v1');await self.registration.unregister();})());});
