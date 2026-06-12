import urllib.request, urllib.parse, json

BASE = 'http://localhost:8000'

subject_variants = json.dumps(['Quick question for {{business}}'])
body_text = 'Hi {{name}},\n\nI saw {{business}} and wanted to reach out.\n\nBest,\n{{sender_name}}\n\nUnsubscribe: {{unsubscribe_link}}'

params = urllib.parse.urlencode({
    'name': 'Test Template',
    'template_type': 'initial',
    'subject_variants': subject_variants,
    'body': body_text,
    'ab_test_enabled': 'false'
})

# 1. Create template
req = urllib.request.Request(BASE + '/api/templates?' + params, method='POST')
with urllib.request.urlopen(req) as r:
    template = json.loads(r.read())
    tid = template['id']
    print('OK: Template created id=' + str(tid) + ' name=' + template['name'])

# 2. Spam check
req2 = urllib.request.Request(BASE + '/api/templates/' + str(tid) + '/spam-check', method='POST')
with urllib.request.urlopen(req2) as r:
    spam = json.loads(r.read())
    print('OK: Spam score=' + str(spam['score']) + '/10 safe=' + str(spam['is_safe']))

# 3. Preview
req3 = urllib.request.Request(BASE + '/api/templates/' + str(tid) + '/preview', method='POST')
with urllib.request.urlopen(req3) as r:
    preview = json.loads(r.read())
    print('OK: Preview subject=' + preview['subject'])
    print('OK: Has unsubscribe=' + str(preview['has_unsubscribe']))

# 4. Delete (cleanup)
req4 = urllib.request.Request(BASE + '/api/templates/' + str(tid), method='DELETE')
with urllib.request.urlopen(req4) as r:
    result = json.loads(r.read())
    print('OK: Cleanup done - ' + result['message'])

print('')
print('=== Full pipeline: ALL PASSED ===')
