// Onboarding flow — conversational profile builder
let conversationId = null;
let currentStep = 0;
let profileData = {};

const ONBOARDING_STEPS = [
    {
        question: "What's your name?",
        field: "name",
        type: "text",
    },
    {
        question: "When were you born? (YYYY-MM-DD)",
        field: "date_of_birth",
        type: "text",
    },
    {
        question: "What's your current weight in kg?",
        field: "weight_kg",
        type: "number",
    },
    {
        question: "How many years have you been training seriously?",
        field: "years_experience",
        type: "number",
    },
    {
        question: "Tell me about your training background — what sports, what level, what kind of training have you done?",
        field: "training_background",
        type: "textarea",
    },
    {
        question: "What has worked well for you in training? What approaches, sessions, or routines have given you the best results?",
        field: "what_worked",
        type: "textarea",
    },
    {
        question: "What hasn't worked? Any patterns of injury, burnout, or training approaches that didn't suit you?",
        field: "what_didnt_work",
        type: "textarea",
    },
    {
        question: "What are your current goals? Be specific — races, times, distances, or general fitness targets.",
        field: "current_goals",
        type: "textarea",
    },
    {
        question: "How many hours per week do you want to train? Give me a range (e.g., 10-15).",
        field: "weekly_hours",
        type: "text",
        parse: (val) => {
            const parts = val.split('-').map(s => parseFloat(s.trim()));
            if (parts.length === 2) {
                return { weekly_hours_target_low: parts[0], weekly_hours_target_high: parts[1] };
            }
            return { weekly_hours_target_low: parts[0] - 2, weekly_hours_target_high: parts[0] + 2 };
        }
    },
    {
        question: "What time do you typically finish work? (e.g., 18:00, 22:00)",
        field: "work_finish_time_baseline",
        type: "text",
    },
    {
        question: "How many hours do you typically work per week?",
        field: "work_hours_baseline",
        type: "number",
    },
];

document.addEventListener('DOMContentLoaded', async () => {
    // Check if already onboarded
    try {
        const status = await Coach.get('/athlete/onboarding-status');
        if (status.complete) {
            window.location.href = '/';
            return;
        }
    } catch (e) { /* Continue with onboarding */ }

    const input = document.getElementById('onboarding-input');
    const sendBtn = document.getElementById('onboarding-send');

    sendBtn.addEventListener('click', handleAnswer);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleAnswer();
        }
    });

    // Start first question
    showQuestion();
});

function showQuestion() {
    if (currentStep >= ONBOARDING_STEPS.length) {
        finishOnboarding();
        return;
    }

    const step = ONBOARDING_STEPS[currentStep];
    appendMessage('coach', step.question);
}

async function handleAnswer() {
    const input = document.getElementById('onboarding-input');
    const text = input.value.trim();
    if (!text) return;

    appendMessage('user', text);
    input.value = '';

    const step = ONBOARDING_STEPS[currentStep];

    // Parse and store the answer
    if (step.parse) {
        Object.assign(profileData, step.parse(text));
    } else if (step.type === 'number') {
        profileData[step.field] = parseFloat(text);
    } else {
        profileData[step.field] = text;
    }

    currentStep++;

    if (currentStep < ONBOARDING_STEPS.length) {
        setTimeout(showQuestion, 400);
    } else {
        await finishOnboarding();
    }
}

async function finishOnboarding() {
    appendMessage('coach', "Great — I have everything I need. Setting up your profile...");

    // Add defaults
    profileData.gender = 'M';
    profileData.timezone = 'Europe/Oslo';
    profileData.location_lat = 63.43;
    profileData.location_lon = 10.40;
    profileData.onboarding_complete = 1;
    profileData.intervals_athlete_id = 'i225683';

    try {
        await Coach.post('/athlete/profile', profileData);

        // Trigger initial sync
        appendMessage('coach', "Profile saved! Now syncing your training data from Intervals.icu...");
        try {
            const sync = await Coach.post('/activities/sync', { days: 90 });
            appendMessage('coach', `Synced ${sync.activities} activities and ${sync.wellness} wellness records. Let's go — redirecting to your dashboard.`);
        } catch (e) {
            appendMessage('coach', "Data sync had an issue, but your profile is saved. You can sync from Settings later.");
        }

        setTimeout(() => window.location.href = '/', 2000);
    } catch (e) {
        appendMessage('coach', "Something went wrong saving your profile. Please try again.");
        console.error('Onboarding error:', e);
    }
}

function appendMessage(role, text) {
    const container = document.getElementById('onboarding-messages');
    const msg = document.createElement('div');
    msg.className = `chat-msg chat-msg-${role === 'coach' ? 'coach' : 'user'}`;
    msg.textContent = text;
    container.appendChild(msg);
    container.scrollTop = container.scrollHeight;
}
