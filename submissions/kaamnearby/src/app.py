from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

@app.route('/')
def home():
    return render_template_string('''
        <h1>KaamNearby</h1>
        <p>Find local skilled workers near you.</p>
        <ul>
            <li>Electrician</li>
            <li>Plumber</li>
            <li>Painter</li>
            <li>Cleaner</li>
            <li>Repair Service</li>
        </ul>
        <form method="post" action="/book">
            <input type="text" name="service" placeholder="Service required" required><br><br>
            <input type="text" name="location" placeholder="Your area" required><br><br>
            <button type="submit">Find Worker</button>
        </form>
    ''')

@app.route('/book', methods=['POST'])
def book():
    service = request.form.get('service')
    location = request.form.get('location')
    return f"Booking request received for {service} in {location}. Worker matching will be shown in the next phase."

if __name__ == '__main__':
    app.run(debug=True)
