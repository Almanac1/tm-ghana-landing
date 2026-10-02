document.addEventListener('DOMContentLoaded', () => {
  const body = document.getElementById('id_body');
  if (!body) return;

  const toolbar = document.createElement('div');
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'button';
  button.textContent = 'Insert link';
  button.setAttribute('aria-controls', body.id);
  toolbar.appendChild(button);
  body.before(toolbar);

  button.addEventListener('click', () => {
    const start = body.selectionStart;
    const end = body.selectionEnd;
    const label = body.value.slice(start, end);
    if (!label || /[\[\]\n\r]/.test(label)) {
      window.alert('Select the words you want to link in the Body field first.');
      body.focus();
      return;
    }
    const entered = window.prompt('Enter a full https:// URL or a site path such as /#booking:');
    if (entered === null) return;
    const url = entered.trim();
    if (!/^(https?:\/\/[^/\s]+|\/(?!\/)|#)/i.test(url) || /[\s()\\]/.test(url)) {
      window.alert('Enter a valid web URL, site path, or page anchor.');
      return;
    }
    body.setRangeText(`[${label}](${url})`, start, end, 'select');
    body.dispatchEvent(new Event('input', { bubbles: true }));
    body.focus();
  });
});
