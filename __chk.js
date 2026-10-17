const fs = require('fs'), vm = require('vm');
const h = fs.readFileSync('index.html', 'utf8');
const m = [...h.matchAll(/<script>([\s\S]*?)<\/script>/g)];
let ok = true;
m.forEach((x, i) => { try { new vm.Script(x[1]); } catch (e) { ok = false; console.log('SCRIPT', i, 'ERR:', e.message); } });
console.log(ok ? 'INLINE SCRIPTS OK (' + m.length + ' blocks)' : 'SYNTAX ERRORS');
const need = ['第一步·先拆解原文', '情绪曲线', '钩子类型一致', '最后自检', '按标题+爆款骨架仿写', '将按原文钩子/结构/情绪曲线仿写'];
need.forEach(k => { if (!h.includes(k)) console.log('MISSING:', k); });
console.log('MARKS CHECK DONE');
