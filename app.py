from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector

app = Flask(__name__)
app.secret_key = "cgpa-secret-key"


def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",
        database="cgpa_calculator"
    )


grade_points = {
    "S": 10,
    "A+": 9,
    "A": 8,
    "B+": 7,
    "B": 6.5,
    "C+": 6,
    "C": 5
}


def marks_to_grade_point(marks):
    if marks >= 90:
        return 10
    elif marks >= 80:
        return 9
    elif marks >= 70:
        return 8
    elif marks >= 60:
        return 7
    elif marks >= 50:
        return 6
    elif marks >= 40:
        return 5
    else:
        return 0


@app.route("/")
def home():

    student_name = ""

    if "student_id" in session:

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            "SELECT name FROM students WHERE id = %s",
            (session["student_id"],)
        )

        student = cursor.fetchone()

        cursor.close()
        db.close()

        if student:
            student_name = student[0]

    return render_template(
        "index.html",
        student_name=student_name
    )


@app.route("/calculate", methods=["POST"])
def calculate():

    student_name = request.form.get("student_name", "").strip()
    semester = request.form.get("semester")
    calculation_type = request.form.get("calculation_type")

    if not student_name:
        return "Please enter student name."

    if not semester or not semester.isdigit():
        return "Please enter a valid semester."

    semester = int(semester)

    if semester < 1:
        return "Semester must be 1 or above."

    subject_names = request.form.getlist("subject_name")
    credits = request.form.getlist("credits")
    grades = request.form.getlist("grade")
    marks = request.form.getlist("marks")

    if len(subject_names) == 0:
        return "Please add at least one subject."

    db = get_db_connection()
    cursor = db.cursor()

    # Find existing student
    cursor.execute(
        "SELECT id FROM students WHERE name = %s",
        (student_name,)
    )

    student = cursor.fetchone()

    if student:
        student_id = student[0]

    else:
        cursor.execute(
            "INSERT INTO students (name) VALUES (%s)",
            (student_name,)
        )

        student_id = cursor.lastrowid

    session["student_id"] = student_id

    # Delete old data of the same semester
    cursor.execute(
        """
        DELETE FROM subjects
        WHERE student_id = %s
        AND semester = %s
        """,
        (student_id, semester)
    )

    for i in range(len(subject_names)):

        subject_name = subject_names[i].strip()

        if not subject_name:
            return "Subject name cannot be empty."

        try:
            credit = float(credits[i])
        except ValueError:
            return "Invalid credit."

        if credit <= 0:
            return "Credit must be greater than zero."

        if calculation_type == "grade":

            grade = grades[i]

            if grade not in grade_points:
                return "Invalid grade."

            point = grade_points[grade]
            mark = None

        elif calculation_type == "marks":

            try:
                mark = float(marks[i])
            except ValueError:
                return "Invalid marks."

            if mark < 0 or mark > 100:
                return "Marks must be between 0 and 100."

            point = marks_to_grade_point(mark)
            grade = None

        else:
            return "Invalid calculation type."

        cursor.execute(
            """
            INSERT INTO subjects
            (
                student_id,
                semester,
                subject_name,
                credits,
                calculation_type,
                grade,
                marks,
                grade_point
            )
            VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                student_id,
                semester,
                subject_name,
                credit,
                calculation_type,
                grade,
                mark,
                point
            )
        )

    db.commit()

    cursor.close()
    db.close()

    return redirect(
        url_for(
            "result",
            student_id=student_id
        )
    )


@app.route("/result/<int:student_id>")
def result(student_id):

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Student
    cursor.execute(
        """
        SELECT id, name
        FROM students
        WHERE id = %s
        """,
        (student_id,)
    )

    student = cursor.fetchone()

    if not student:
        cursor.close()
        db.close()
        return "Student not found."

    # Semester results
    cursor.execute(
        """
        SELECT
            semester,
            SUM(credits) AS total_credits,
            SUM(credits * grade_point) AS total_points
        FROM subjects
        WHERE student_id = %s
        GROUP BY semester
        ORDER BY semester
        """,
        (student_id,)
    )

    rows = cursor.fetchall()

    semester_results = []

    overall_credits = 0
    overall_points = 0

    for row in rows:

        total_credits = row["total_credits"]
        total_points = row["total_points"]

        sgpa = total_points / total_credits

        semester_results.append(
            {
                "semester": row["semester"],
                "credits": total_credits,
                "sgpa": sgpa
            }
        )

        overall_credits += total_credits
        overall_points += total_points

    if overall_credits > 0:
        overall_cgpa = overall_points / overall_credits
    else:
        overall_cgpa = 0

    cursor.close()
    db.close()

    return render_template(
        "result.html",
        student=student,
        semester_results=semester_results,
        overall_cgpa=overall_cgpa
    )


if __name__ == "__main__":
    app.run(debug=True)