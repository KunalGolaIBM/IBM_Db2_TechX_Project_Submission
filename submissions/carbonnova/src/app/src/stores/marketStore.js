import { create } from 'zustand';
import { 
  mockListings, 
  mockSensorReadings as initialReadings,
  platformStats as initialStats,
  generateSparklineData
} from '../lib/mockData';
import { useNotificationStore } from './notificationStore';

// Helper to simulate slight reading variations
const addJitter = (val, variance = 0.02) => {
  return +(val * (1 + (Math.random() - 0.5) * variance)).toFixed(2);
};

export const useMarketDataStore = create((set, get) => ({
  listings: mockListings,
  sensorReadings: initialReadings,
  platformStats: initialStats,
  
  // Historical reading arrays for sparklines (simplified for mock)
  history: Object.keys(initialReadings).reduce((acc, devId) => {
    acc[devId] = {
      co2: generateSparklineData(initialReadings[devId].co2_ppm, 0.05).map(i => i.value),
      soil: generateSparklineData(initialReadings[devId].soil_moisture_pct, 0.02).map(i => i.value),
      pm25: generateSparklineData(initialReadings[devId].pm25, 0.1).map(i => i.value),
      humidity: generateSparklineData(initialReadings[devId].humidity_pct, 0.03).map(i => i.value),
    };
    return acc;
  }, {}),

  // Called to start interval simulating Supabase Realtime
  startSimulation: () => {
    // Only start once
    if (get().simInterval) return;

    const intervalId = setInterval(() => {
      set((state) => {
        const newReadings = { ...state.sensorReadings };
        const newHistory = { ...state.history };
        let listingsChanged = false;
        
        let newListings = [...state.listings];

        // Simulate new reading for every device
        Object.keys(newReadings).forEach(devId => {
          const old = newReadings[devId];
          
          // Randomly trigger anomaly (1% chance per tick)
          const isAnomaly = Math.random() < 0.01;
          
          if (isAnomaly) {
             console.log(`[IoT Simulator] Anomaly detected on device ${devId}`);
             useNotificationStore.getState().addNotification(
                'Sensor Anomaly', 
                `Unusual readings detected on device ${devId}. Quality score flagged.`, 
                'warning'
             );
          }

          newReadings[devId] = {
            ...old,
            co2_ppm: isAnomaly ? old.co2_ppm * 1.5 : addJitter(old.co2_ppm, 0.01),
            temperature_c: addJitter(old.temperature_c, 0.02),
            humidity_pct: addJitter(old.humidity_pct, 0.01),
            soil_moisture_pct: addJitter(old.soil_moisture_pct, 0.01),
            pm25: isAnomaly ? old.pm25 * 3 : addJitter(old.pm25, 0.05),
          };

          // Update histories
          newHistory[devId].co2 = [...newHistory[devId].co2.slice(1), newReadings[devId].co2_ppm];
          newHistory[devId].soil = [...newHistory[devId].soil.slice(1), newReadings[devId].soil_moisture_pct];
          newHistory[devId].pm25 = [...newHistory[devId].pm25.slice(1), newReadings[devId].pm25];
          newHistory[devId].humidity = [...newHistory[devId].humidity.slice(1), newReadings[devId].humidity_pct];

          // Re-calculate quality score (simplified mock logic)
          // Find lists tied to this project (mocking project-device link simply)
          
          newListings = newListings.map(listing => {
            // Rough logic to map dev-1->proj-1->lst-1, dev-2->proj-2->lst-2...
            const listingDevId = `dev-${listing.id.split('-')[1]}`;
            if (devId === listingDevId) {
              
              let newScore = listing.quality_score;
              if (isAnomaly) {
                newScore = Math.max(0, newScore - 15);
              } else {
                 // Slowly trend towards baseline based on reading
                 const co2Factor = newReadings[devId].co2_ppm < 400 ? 1 : -1;
                 if (Math.random() > 0.5) {
                    newScore = Math.min(100, Math.max(0, newScore + co2Factor));
                 }
              }

              // Update tier
              let newTier = 'gold';
              if (newScore < 45) newTier = 'flagged';
              else if (newScore < 65) newTier = 'bronze';
              else if (newScore < 85) newTier = 'silver';

              if (newScore !== listing.quality_score) {
                 listingsChanged = true;
              }

              return {
                ...listing,
                quality_score: newScore,
                quality_tier: newTier,
                last_score_update: new Date().toISOString()
              };
            }
            return listing;
          });
        });

        return {
          sensorReadings: newReadings,
          history: newHistory,
          listings: newListings,
        };
      });
    }, 5000); // Tick every 5 seconds

    set({ simInterval: intervalId });
  },

  stopSimulation: () => {
    const interval = get().simInterval;
    if (interval) {
      clearInterval(interval);
      set({ simInterval: null });
    }
  }
}));
