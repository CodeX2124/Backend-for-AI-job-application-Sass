# app/models.py
from flask_login import UserMixin
from .extensions import supabase

class User(UserMixin):
    def __init__(self, user_id, is_first_login=True, real_name=None, email=None, preferred_roles_responsibilities=None, is_subscribed=False, stripe_customer_id=None, cancel_at_period_end=None, last_login=None):
        # Ensure user_id is a string and handle dictionary case
        if isinstance(user_id, dict):
            self.id = str(user_id.get('id'))
        else:
            self.id = str(user_id)
        self.real_name = real_name
        self.preferred_roles_responsibilities = preferred_roles_responsibilities
        self.email = email
        self._is_subscribed = is_subscribed
        self.stripe_customer_id = stripe_customer_id
        self.cancel_at_period_end = cancel_at_period_end
        self.last_login = last_login
        self.is_first_login = is_first_login

    @property
    def is_subscribed(self):
        return self._is_subscribed

    @is_subscribed.setter
    def is_subscribed(self, value):
        self._is_subscribed = value

    def get_id(self):
        """Required by Flask-Login"""
        return str(self.id)

    @staticmethod
    def get(user_id):
        # Handle different user_id formats
        if isinstance(user_id, dict):
            user_id = user_id.get('id')
        elif isinstance(user_id, str) and len(user_id) > 36:
            try:
                import ast
                user_dict = ast.literal_eval(user_id)
                user_id = user_dict.get('id')
            except:
                pass
        
        try:
            response = supabase.table('profiles').select('*').eq('id', user_id).execute()
            # Query job_preferences table for real_name
            job_preferences_response = supabase.table('user_job_preferences').select('real_name', 'preferred_roles_responsibilities').eq('user_id', user_id).execute()
            
            real_name = None
            if job_preferences_response.data:
                real_name = job_preferences_response.data[0].get('real_name')
                preferred_roles_responsibilities = job_preferences_response.data[0].get('preferred_roles_responsibilities')
            if response.data:
                user_data = response.data[0]
                return User(
                    user_id=user_data['id'],
                    real_name=real_name,
                    preferred_roles_responsibilities=preferred_roles_responsibilities,
                    email=user_data.get('email'),
                    is_first_login=user_data.get('is_first_login'),
                    is_subscribed=user_data.get('is_subscribed', False),
                    stripe_customer_id=user_data.get('stripe_customer_id'),
                    cancel_at_period_end=user_data.get('cancel_at_period_end'),
                    last_login=user_data.get('last_login')
                )
            return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None

    @staticmethod
    def get_by_email(email):
        try:
            response = supabase.table('profiles').select('*').eq('email', email).execute()
            if response.data:
                user_data = response.data[0]
                return User(
                    user_id=user_data['id'],
                    email=user_data.get('email'),
                    is_subscribed=user_data.get('is_subscribed', False),
                    stripe_customer_id=user_data.get('stripe_customer_id'),
                    cancel_at_period_end=user_data.get('cancel_at_period_end'),
                    last_login=user_data.get('last_login')
                )
            return None
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None