import type { Feature, FeatureCollection, Polygon } from "geojson";

export type DroughtSeverity = 0 | 1 | 2 | 3 | 4 | 5;

export interface MockDroughtProperties {
  name: string;
  severity: DroughtSeverity;
  label: string;
}

export type MockDroughtFeature = Feature<Polygon, MockDroughtProperties>;
export type MockDroughtFeatureCollection = FeatureCollection<
  Polygon,
  MockDroughtProperties
>;

export const mockDroughtGeoJson: MockDroughtFeatureCollection = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: {
        name: "Gulf Coast Exceptional Drought",
        severity: 5,
        label: "Exceptional Drought",
      },
      geometry: {
        type: "Polygon",
        coordinates: [[
          [-98.5, 31.5],
          [-95.0, 31.2],
          [-91.0, 30.8],
          [-89.0, 29.8],
          [-89.5, 28.8],
          [-92.0, 28.6],
          [-95.5, 28.7],
          [-98.0, 29.2],
          [-99.0, 30.2],
          [-98.5, 31.5],
        ]],
      },
    }
  ],
};