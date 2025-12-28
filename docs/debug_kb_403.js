/* 
 * 知识库403错误诊断脚本
 * 在浏览器Console中运行此脚本
 */

console.log('=== 知识库403错误诊断 ===\n');

// 1. 检查所有可能的token
console.log('1. 检查Token存储:');
const tokens = {
  'auth_token': localStorage.getItem('auth_token'),
  'access_token': localStorage.getItem('access_token'),
  'token': localStorage.getItem('token')
};

for (const [key, value] of Object.entries(tokens)) {
  if (value) {
    console.log(`  ✓ ${key}: ${value.substring(0, 20)}...`);
  } else {
    console.log(`  ✗ ${key}: 未设置`);
  }
}

// 2. 检查用户信息
console.log('\n2. 检查用户信息:');
const userStr = localStorage.getItem('user');
if (userStr) {
  try {
    const user = JSON.parse(userStr);
    console.log('  用户名:', user.username);
    console.log('  角色:', user.role);
  } catch (e) {
    console.log('  ✗ 用户信息解析失败');
  }
} else {
  console.log('  ✗ 未找到用户信息');
}

// 3. 测试权限API
console.log('\n3. 测试权限API:');
fetch('/api/permissions/me/permissions')
  .then(r => {
    console.log(`  权限API状态: ${r.status} ${r.statusText}`);
    return r.json();
  })
  .then(data => {
    console.log(`  权限数量: ${data.length || 0}`);
    const kbPerms = data.filter(p => p.code && p.code.startsWith('kb'));
    console.log(`  知识库权限: ${kbPerms.length}`);
    if (kbPerms.length > 0) {
      kbPerms.forEach(p => console.log(`    - ${p.code}: ${p.name}`));
    }
  })
  .catch(err => console.error('  ✗ 错误:', err.message));

// 4. 测试知识库API（带详细错误）
console.log('\n4. 测试知识库API:');
fetch('/api/kb', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('auth_token') || localStorage.getItem('token') || ''}`
  }
})
  .then(async r => {
    console.log(`  知识库API状态: ${r.status} ${r.statusText}`);
    const text = await r.text();
    if (r.status === 403) {
      console.log('  ✗ 403错误响应:', text);
    } else if (r.ok) {
      const data = JSON.parse(text);
      console.log(`  ✓ 成功! 知识库数量: ${data.length}`);
    }
    return text;
  })
  .catch(err => console.error('  ✗ 错误:', err.message));

// 5. 检查请求头
console.log('\n5. 当前请求会使用的token:');
const token = localStorage.getItem('auth_token') || 
              localStorage.getItem('access_token') || 
              localStorage.getItem('token');
if (token) {
  console.log(`  Token (前20字符): ${token.substring(0, 20)}...`);
  console.log(`  Token长度: ${token.length}`);
} else {
  console.log('  ✗ 未找到任何token');
}

console.log('\n=== 诊断完成 ===');
console.log('\n如果看到403错误，可能的原因:');
console.log('1. Token未设置或已过期');
console.log('2. Token格式不正确');
console.log('3. 后端权限检查逻辑有问题');
console.log('\n建议操作:');
console.log('1. 重新登录: window.location.href = "/login"');
console.log('2. 清除并重新登录: localStorage.clear(); window.location.href = "/login"');

