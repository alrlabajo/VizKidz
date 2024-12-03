from django.shortcuts import render, redirect
from .forms import LoginForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth import authenticate, login, logout

import matplotlib

matplotlib.use('Agg')  # Use non-GUI backend to avoid Tcl/Tk errors

from django.shortcuts import render
from django.http import HttpResponse
from .forms import FileUploadForm, ChartTypeForm
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from fpdf import FPDF
import os

# In-memory storage for the file and chart
uploaded_data = {}
chart_image_base64 = None
report_content = None


def welcome(request):    
    return render(request, "welcome.html")

@csrf_protect
def signup_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect("signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose a different username.")
            return redirect("signup")

        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists. Please use a different email.")
            return redirect("signup")

        user_creds = User.objects.create_user(username=username, email=email, password=password1)
        user_creds.save()

        messages.success(request, "Account created successfully")
        return redirect("signin")

    return render(request, "signup.html")

@csrf_protect
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                form.add_error(None, "Invalid username or password")
    elif request.method == 'GET' and 'logout' in request.GET:
        # Check if logout action is in the GET request
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect('signin')  # Redirect to the login page after logout
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})


# Dashboard view
@login_required(login_url='signin')
def dashboard(request):
    context = {
        'username': request.user.username,
    }
    return render(request, 'dashboard.html', context)

@login_required(login_url='signin')
def generate_chart(request):
        global uploaded_data, chart_image_base64, report_content

        # Initialize forms
        upload_form = FileUploadForm(request.POST or None, request.FILES or None)
        chart_form = ChartTypeForm(request.POST or None)

        # Step 1: File Upload
        if request.method == "POST" and "upload" in request.POST:
            if upload_form.is_valid():
                uploaded_file = request.FILES['file']
                ext = os.path.splitext(uploaded_file.name)[1]

                # Load the file into pandas DataFrame
                if ext == '.csv':
                    uploaded_data['df'] = pd.read_csv(uploaded_file)
                elif ext in ['.xls', '.xlsx']:
                    uploaded_data['df'] = pd.read_excel(uploaded_file)
                else:
                    return HttpResponse("Unsupported file format.")

        # Step 3: Chart Generation
        if request.method == "POST" and "generate_chart" in request.POST:
            if chart_form.is_valid() and 'df' in uploaded_data:
                chart_type = chart_form.cleaned_data['chart_type']
                x_column = request.POST.get('x_column', uploaded_data['df'].columns[0])  # Default to first column
                y_column = request.POST.get('y_column')

                df = uploaded_data['df'].copy()  # Create a copy to avoid modifying original DataFrame

                if x_column not in df.columns:
                    return HttpResponse(f"Invalid x-axis column: {x_column}")
                if y_column and y_column not in df.columns:
                    return HttpResponse(f"Invalid y-axis column: {y_column}")

                # Use x_column for x-axis and y_column for y-axis (default to first numeric column if not specified)
                x_values = df[x_column]
                y_values = df[y_column] if y_column else df.select_dtypes(include='number').iloc[:, 0]

                plt.figure(figsize=(10, 6))

                if chart_type == 'line':
                    plt.plot(x_values, y_values, marker='o', linestyle='-', color='b')  # Add points to line chart
                elif chart_type == 'bar':
                    plt.bar(x_values, y_values)
                elif chart_type == 'pie':
                    plt.pie(y_values, labels=x_values, autopct='%1.1f%%')
                elif chart_type == 'doughnut':
                    wedges, texts, autotexts = plt.pie(
                        y_values, labels=x_values, autopct='%1.1f%%', wedgeprops=dict(width=0.4)
                    )
                elif chart_type == 'time':
                    # Validate time series columns
                    time_related_keywords = ['date', 'month', 'year', 'day', 'time']
                    valid_time_columns = [col for col in df.columns if
                                        any(keyword in col.lower() for keyword in time_related_keywords)]

                    if not valid_time_columns:
                        return HttpResponse("No valid date-related column found for Time Series Chart.")

                    x_column = valid_time_columns[0]
                    df[x_column] = pd.to_datetime(df[x_column], errors='coerce')
                    if df[x_column].isnull().all():
                        return HttpResponse("The selected date-related column cannot be parsed as datetime.")

                    # Plot the time series like a line chart
                    y_values = df.select_dtypes(include='number').iloc[:, 0]  # Select the first numeric column
                    plt.plot(df[x_column], y_values, marker='o', linestyle='-', color='b')  # Similar to line chart

                plt.title(f"{chart_type.capitalize()} Chart")
                buffer = BytesIO()
                plt.savefig(buffer, format='png')
                buffer.seek(0)
                chart_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                buffer.close()

                # Generate the short paragraph description for the report
                if chart_type == 'line':
                    report_content = f"The line chart visualizes the relationship between {x_column} and {y_column if y_column else 'the first numeric column'} over time or categories. The data shows some fluctuations, with a peak at {y_values.max()} and a drop at {y_values.min()}."
                elif chart_type == 'bar':
                    report_content = f"The bar chart compares the values of {y_column if y_column else 'the first numeric column'} across different categories of {x_column}. The chart highlights the highest value in the category {x_values[y_values.idxmax()]} and the lowest value in {x_values[y_values.idxmin()]}, indicating a significant variation."
                elif chart_type == 'pie':
                    report_content = f"The pie chart illustrates the proportion of {y_column if y_column else 'the first numeric column'} across different categories of {x_column}. The largest slice represents {x_values[y_values.idxmax()]}, while the smallest represents {x_values[y_values.idxmin()]}, showing the relative contribution of each category."
                elif chart_type == 'doughnut':
                    report_content = f"The doughnut chart displays the distribution of {y_column if y_column else 'the first numeric column'} across categories in {x_column}. The chart provides a visual breakdown of the proportions, with {x_values[y_values.idxmax()]} having the largest share."
                elif chart_type == 'time':
                    report_content = f"The time series chart presents the changes in {y_column if y_column else 'the first numeric column'} over time, with {x_column} as the time axis. The data shows a clear trend, with notable fluctuations occurring around {df[x_column].min()} and {df[x_column].max()}."

        # Step 5: Export Chart to PDF
        if request.method == "POST" and "export_pdf" in request.POST and chart_image_base64:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)

            # Title and report content
            pdf.cell(w=200, h=10, txt="Data Visualization Report", ln=True)
            pdf.ln(10)  # Add space before report content
            pdf.multi_cell(0, 10, report_content)

            # Add the chart image
            chart_path = "chart.png"
            with open(chart_path, "wb") as f:
                f.write(base64.b64decode(chart_image_base64))
            pdf.image(chart_path, x=10, y=90, w=190)
            os.remove(chart_path)

            response = HttpResponse(content_type="application/pdf")
            response['Content-Disposition'] = 'attachment; filename="data_visualization_report.pdf"'
            response.write(pdf.output(dest='S').encode('latin1'))
            return response

        # Render the dashboard template
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        if 'df' in uploaded_data:
            df = uploaded_data['df']
            df.index = range(1, len(df) + 1)  # Reset index to start from 1
            preview_data = df.to_html(index=True)  # Include the adjusted index in the preview
            column_options = df.columns.tolist()  # Extract column names for selection
        else:
            preview_data = None
            column_options = None

        return render(request, 'generate_chart.html', {
            'upload_form': upload_form,
            'chart_form': chart_form,
            'preview_data': preview_data,
            'chart_image': chart_image_base64,
            'column_options': column_options,
            'report_content': report_content,  # Send the short paragraph report for preview
        })