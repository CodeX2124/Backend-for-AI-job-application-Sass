from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, IntegerField, SubmitField, 
    RadioField, HiddenField, FieldList, FormField
)
from wtforms.validators import DataRequired, NumberRange, Optional, Email, Length

class ProfileForm(FlaskForm):
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    profile_name = StringField('Profile Name', validators=[DataRequired(), Length(max=100)])
    postnomial = StringField('Postnomials', validators=[Optional(), Length(max=50)])
    contact_email = StringField('Email', validators=[DataRequired(), Email(), Length(max=100)])
    contact_phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    current_city = StringField('City', validators=[DataRequired(), Length(max=50)])
    current_state = StringField('State', validators=[DataRequired(), Length(max=50)])


class JobFiltersForm(FlaskForm):
    ideal_work_situation = TextAreaField('Ideal Work Situation', validators=[Optional(), Length(max=500)])
    preferred_industries = StringField('Preferred Industries (comma-separated)', validators=[Optional(), Length(max=500)])
    preferred_roles_responsibilities = StringField('Preferred Roles and Responsibilities (comma-separated)', validators=[Optional(), Length(max=500)])
    work_arrangement_preference = SelectField(
        'Work Arrangement Preference',
        choices=[('remote', 'Remote'), ('onsite', 'Onsite'), ('hybrid', 'Hybrid')],
        validators=[Optional()]
    )
    willing_to_relocate = SelectField(
        'Willing to Relocate',
        choices=[('yes', 'Yes'), ('no', 'No')],
        validators=[DataRequired()]
    )
    relocation_preference = SelectField(
        'Relocation Preference',
        choices=[('anywhere', 'Anywhere'), ('specific', 'Specific')],
        validators=[Optional()]
    )
    preferred_locations = StringField(
        'Preferred Locations (JSON or comma-separated)',
        validators=[Optional(), Length(max=1000)]
    )
    expected_salary_range = StringField('Expected Salary Range', validators=[Optional(), Length(max=50)])

class WorkExperienceEntryForm(FlaskForm):
    company = StringField('Company', validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()], render_kw={"rows": 3})
    start_month = SelectField('Start Month', choices=[(str(i), str(i)) for i in range(1, 13)], validators=[DataRequired()])
    start_year = IntegerField('Start Year', validators=[DataRequired()])
    end_month = SelectField('End Month', choices=[('', 'No End')] + [(str(i), str(i)) for i in range(1, 13)], validators=[Optional()])
    end_year = IntegerField('End Year', validators=[Optional()])

class EducationEntryForm(FlaskForm):
    institution = StringField('Institution', validators=[DataRequired()])
    degree = SelectField('Degree', choices=[('bachelor', 'Bachelor'),
('master', 'Master'),
('doctorate', 'Doctorate'),
('associate', 'Associate')], validators=[DataRequired()])
    degree_title = SelectField(
        'Degree Title',
        choices=[
            ('BA', 'Bachelor of Arts'),
            ('BS', 'Bachelor of Science'),
            ('BSc', 'Bachelor of Science'),
            ('BBA', 'Bachelor of Business Administration'),
            ('BFA', 'Bachelor of Fine Arts'),
            ('BMus', 'Bachelor of Music'),
            ('BEd', 'Bachelor of Education'),
            ('BEng', 'Bachelor of Engineering'),
            ('BSN', 'Bachelor of Science in Nursing'),

            ('MA', 'Master of Arts'),
            ('MS', 'Master of Science'),
            ('MSc', 'Master of Science'),
            ('MBA', 'Master of Business Administration'),
            ('MFA', 'Master of Fine Arts'),
            ('MEd', 'Master of Education'),
            ('MPH', 'Master of Public Health'),
            ('MSW', 'Master of Social Work'),
            ('MMus', 'Master of Music'),
            ('MEng', 'Master of Engineering'),

            ('PhD', 'Doctor of Philosophy'),
            ('EdD', 'Doctor of Education'),
            ('DBA', 'Doctor of Business Administration'),
            ('MD', 'Doctor of Medicine'),
            ('JD', 'Juris Doctor (Law)'),
            ('DDS', 'Doctor of Dental Surgery'),
            ('DVM', 'Doctor of Veterinary Medicine'),
            ('PsyD', 'Doctor of Psychology'),

            ('PostDoc', 'Post-Doctoral Fellow/Research'),
            ('PDF', 'Post-Doctoral Fellowship')
        ]
    )
    field_of_study = StringField('Field of Study', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()], render_kw={"rows": 3})
    start_month = SelectField('Start Month', choices=[(str(i), str(i)) for i in range(1, 13)], validators=[DataRequired()])
    start_year = IntegerField('Start Year', validators=[DataRequired()])
    end_month = SelectField('End Month', choices=[('', 'No End')] + [(str(i), str(i)) for i in range(1, 13)], validators=[Optional()])
    end_year = IntegerField('End Year', validators=[Optional()])

class CertificationEntryForm(FlaskForm):
    title = StringField('Certification Title', validators=[DataRequired()])
    issuer = StringField('Issuer', validators=[DataRequired()])
    acquired_date = StringField('Acquired Date (MM/YYYY)', validators=[DataRequired(), Length(max=7)])

def validate_salary(form, field):
    try:
        field.data = int(field.data)
    except ValueError:
        raise ValidationError("Salary must be a numeric value.")

def validate_preferred_locations(form, field):
    if form.willing_to_relocate.data == 'yes' and form.relocation_preference.data == 'specific':
        if not field.data or field.data.strip() == "":
            raise ValidationError("You must specify preferred locations if relocation preference is 'specific'.")
        
class JobPreferencesForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired()])
    postnomial = StringField('Degree Abbreviation (Postnomials)', validators=[Optional()])
    contact_phone = StringField('Phone', validators=[DataRequired(), Length(max=15)])
    contact_email = StringField('Email', validators=[DataRequired(), Email()])
    
    # Living Address
    current_country = SelectField('Country', validators=[Optional()])
    current_state = SelectField('State', validators=[DataRequired()])
    current_city = StringField('City', validators=[DataRequired()])
    current_address = StringField('House Address', validators=[DataRequired()])
    
    work_experience = FieldList(FormField(WorkExperienceEntryForm), min_entries=0, max_entries=3)
    education = FieldList(FormField(EducationEntryForm), min_entries=0, max_entries=3)
    certifications = FieldList(FormField(CertificationEntryForm), min_entries=0, max_entries=3)

    ideal_work_situation = TextAreaField('Describe in your own words your ideal work situation',
                                         validators=[DataRequired()],
                                         render_kw={"rows": 4})
    preferred_industries = StringField('Preferred Industries', validators=[DataRequired()])
    work_arrangement_preference = SelectField('Work Arrangement Preference', 
                                             choices=[('flexible', 'Flexible (open to any)'),
                                                      ('remote', 'Fully Remote Only'),
                                                      ('hybrid', 'Hybrid'),
                                                      ('onsite', 'On-site')],
                                             validators=[DataRequired()])

    willing_to_relocate = RadioField('Are you willing to relocate for a job opportunity?', 
                                     choices=[('yes', 'Yes'), ('no', 'No')],
                                     validators=[DataRequired()])
    relocation_preference = SelectField('Relocation Preference', 
                                        choices=[('anywhere', 'Anywhere'),
                                                 ('specific', 'Specific locations')],
                                        validators=[DataRequired()])
    preferred_locations = StringField(
    'Preferred Locations',
    validators=[Optional(), validate_preferred_locations]
    )
    preferred_roles_responsibilities = StringField('Preferred Roles & Responsibilities', validators=[DataRequired()])
    expected_salary_range = StringField(
        'Expected Salary Range',
        validators=[DataRequired(), validate_salary, NumberRange(min=0, max=300000)], default=150000
    )
    # industry_importance = RadioField('Industry Importance', choices=[(str(i), str(i)) for i in range(1, 6)], validators=[DataRequired()])
    # location_work_arrangement_importance = RadioField('Location and Work Arrangement Importance', choices=[(str(i), str(i)) for i in range(1, 6)], validators=[DataRequired()])
    # role_responsibilities_importance = RadioField('Role & Responsibilities Importance', choices=[(str(i), str(i)) for i in range(1, 6)], validators=[DataRequired()])
    # salary_importance = RadioField('Salary Importance', choices=[(str(i), str(i)) for i in range(1, 6)], validators=[DataRequired()])
    # company_prestige_importance = RadioField('Company Prestige & Reputation Importance', choices=[(str(i), str(i)) for i in range(1, 6)], validators=[DataRequired()])
    submit = SubmitField('Submit Preferences')

    def __init__(self, *args, **kwargs):
        super(JobPreferencesForm, self).__init__(*args, **kwargs)
        self.current_state.choices = [
            ('','(Select)'),
            ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
            ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
            ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'), ('ID', 'Idaho'),
            ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'), ('KS', 'Kansas'),
            ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'), ('MD', 'Maryland'),
            ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'), ('MS', 'Mississippi'),
            ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'), ('NV', 'Nevada'),
            ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'), ('NY', 'New York'),
            ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'), ('OK', 'Oklahoma'),
            ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'), ('SC', 'South Carolina'),
            ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'), ('UT', 'Utah'),
            ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'), ('WV', 'West Virginia'),
            ('WI', 'Wisconsin'), ('WY', 'Wyoming'),
            # U.S. Territories
            ('AS', 'American Samoa'), ('GU', 'Guam'), ('MP', 'Northern Mariana Islands'),
            ('PR', 'Puerto Rico'), ('VI', 'U.S. Virgin Islands'),
            # Other U.S. Possessions
            ('DC', 'District of Columbia'), ('FM', 'Federated States of Micronesia'),
            ('MH', 'Marshall Islands'), ('PW', 'Palau')
        ]
        self.current_country.choices = [
            ('','(Select)'),
            ('USA', 'United States of America')
        ]
