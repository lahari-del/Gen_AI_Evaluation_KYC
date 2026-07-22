import os
from openai import OpenAI

class SchoolOpsAIEngine:
    def __init__(self):
        # Reads key directly from open ai key.txt if present, or environment variable
        try:
            with open("open ai key.txt", "r") as f:
                api_key = f.read().strip()
        except FileNotFoundError:
            api_key = os.environ.get("OPENAI_API_KEY", "")

        self.client = OpenAI(api_key=api_key if api_key else "dummy_key")

    def generate_evaluation_report(self, employee_data: dict) -> dict:
        """Generates performance evaluations based on school operations log data."""
        try:
            if "dummy_key" in self.client.api_key and not os.environ.get("OPENAI_API_KEY"):
                raise ValueError("No valid OpenAI API key detected.")

            prompt = f"""
            You are an Operations Manager for a School Management Software Company.
            Evaluate the employee performance for: {employee_data['NAME']}.
            
            Key Operational Data:
            - Total Tasks Processed: {employee_data['Total Tasks']}
            - Completion Rate: {employee_data['Completion Rate (%)']:.1f}%
            - High-Complexity Tasks Handled: {employee_data['Complex Tasks']}
            - Schools Serviced: {employee_data['Schools Serviced']}
            - Pending/Incomplete Tasks: {employee_data['Pending Tasks']}
            - Overall Weighted Performance Score: {employee_data['Overall Score']:.2f}/100
            
            Generate a 5-section evaluation report with these EXACT headings:
            1. STRENGTHS
            2. AREAS FOR IMPROVEMENT
            3. SCHOOL & OPERATIONAL IMPACT
            4. PROMOTION & SPECIALIZATION READINESS
            5. TARGETED TRAINING RECOMMENDATIONS
            """

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a professional operations manager in EdTech operations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_tokens=1000
            )
            return self._parse_ai_response(response.choices[0].message.content)

        except Exception:
            return self._generate_local_fallback(employee_data)

    def _generate_local_fallback(self, data: dict) -> dict:
        """Offline fallback generator if the API key is not supplied or fails."""
        score = data['Overall Score']
        
        if score >= 85:
            strengths = f"Exemplary productivity handling {data['Total Tasks']} tasks across {data['Schools Serviced']} schools with a {data['Completion Rate (%)']:.1f}% completion rate."
            improvements = "Maintain operational speed while taking on complex school onboarding configurations."
            readiness = "High readiness for Senior Operations Specialist or Onboarding Lead."
        else:
            strengths = f"Maintains active support, servicing {data['Schools Serviced']} schools."
            improvements = f"Needs focus on reducing pending tasks ({data['Pending Tasks']} pending) and boosting overall completion rate."
            readiness = "Recommended to focus on core task resolution speed before scaling responsibilities."

        return {
            "Strengths": strengths,
            "Improvement Areas": improvements,
            "School & Operational Impact": f"Serviced {data['Schools Serviced']} client schools directly. High completion rate directly improves client retention.",
            "Promotion Readiness": readiness,
            "Training Recommendations": "1. Module Training: Fee & Batch Configurations.\n2. Time Management for Priority Tickets."
        }

    def _parse_ai_response(self, text: str) -> dict:
        sections = {"Strengths": "", "Improvement Areas": "", "School & Operational Impact": "", "Promotion Readiness": "", "Training Recommendations": ""}
        current_section = None
        
        for line in text.split('\n'):
            if "STRENGTHS" in line.upper():
                current_section = "Strengths"
            elif "IMPROVEMENT" in line.upper():
                current_section = "Improvement Areas"
            elif "IMPACT" in line.upper():
                current_section = "School & Operational Impact"
            elif "PROMOTION" in line.upper() or "READINESS" in line.upper():
                current_section = "Promotion Readiness"
            elif "TRAINING" in line.upper() or "RECOMMENDATIONS" in line.upper():
                current_section = "Training Recommendations"
            elif current_section and line.strip():
                sections[current_section] += line + "\n"
                
        return sections