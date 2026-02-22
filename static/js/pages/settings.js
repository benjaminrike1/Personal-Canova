// Settings page logic
document.addEventListener('DOMContentLoaded', async () => {
    // Load current profile to fill location fields
    try {
        const profile = await Coach.get('/athlete/profile');
        if (profile) {
            const locForm = document.getElementById('location-form');
            if (profile.location_lat) locForm.querySelector('[name="location_lat"]').value = profile.location_lat;
            if (profile.location_lon) locForm.querySelector('[name="location_lon"]').value = profile.location_lon;

            const intForm = document.getElementById('intervals-form');
            if (profile.intervals_athlete_id) intForm.querySelector('[name="intervals_athlete_id"]').value = profile.intervals_athlete_id;
        }
    } catch (e) { /* no profile yet */ }

    // Location form
    document.getElementById('location-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = {
            location_lat: parseFloat(e.target.querySelector('[name="location_lat"]').value),
            location_lon: parseFloat(e.target.querySelector('[name="location_lon"]').value),
        };
        try {
            await Coach.put('/athlete/profile', data);
            alert('Location saved!');
        } catch (err) {
            alert('Failed to save: ' + err.message);
        }
    });

    // Sync buttons
    document.getElementById('sync-activities').addEventListener('click', async () => {
        const status = document.getElementById('sync-status');
        status.textContent = 'Syncing activities...';
        try {
            const result = await Coach.post('/activities/sync', { days: 30 });
            status.textContent = `Synced ${result.activities} activities and ${result.wellness} wellness records`;
        } catch (e) {
            status.textContent = 'Sync failed: ' + e.message;
        }
    });

    document.getElementById('sync-weather').addEventListener('click', async () => {
        const status = document.getElementById('sync-status');
        status.textContent = 'Syncing weather...';
        try {
            const result = await Coach.post('/weather/sync', { days: 14 });
            status.textContent = `Synced ${result.synced} weather records`;
        } catch (e) {
            status.textContent = 'Weather sync failed: ' + e.message;
        }
    });
});
