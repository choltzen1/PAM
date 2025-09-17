from factory import create_app
app = create_app({'TESTING': True})
for r in sorted(app.url_map.iter_rules(), key=lambda x: x.rule):
    print(r.rule, '->', r.endpoint, 'methods', sorted(r.methods))