// No financial API responses, authentication or HTML are cached.
self.addEventListener('install',event=>event.waitUntil(self.skipWaiting()));
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('push',event=>{
  let data;try{data=event.data.json();}catch{return;}
  event.waitUntil(self.registration.showNotification('A payment needs your attention',{
    body:'Open Wallet-Voice to review it.',icon:'/wallet-icon.svg',tag:data.tag || 'wallet-attention',
    data:{payment_id:data.payment_id},actions:[{action:'review',title:'Review now'}]
  }));
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const url=new URL('/',self.location.origin);url.searchParams.set('review',event.notification.data?.payment_id || '');
  event.waitUntil(self.clients.openWindow(url.href));
});
