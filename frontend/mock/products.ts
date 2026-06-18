import { Product } from '../types/api';

export const mockProducts: Product[] = [
  {
    id: 'prod_bat_pro',
    name: 'Cricket Bat Pro',
    description: 'Professional-grade Kashmir Willow bat designed for power hitting and standard tournament play. Features an ergonomic rubber scale grip and reinforced edges.',
    price: 3999,
    image: '/images/bat_pro.png',
    category: 'Sports Equipment',
    specifications: {
      'Material': 'Selected Kashmir Willow',
      'Grade': 'Grade 2 Premium',
      'Weight': '1150 - 1175g',
      'Grip Type': 'Chevron Scale Rubber',
      'Sweet Spot': 'Mid-to-Low Profile'
    }
  },
  {
    id: 'prod_bat_elite',
    name: 'Cricket Bat Elite',
    description: 'High-performance English Willow bat harvested from premium willow blocks. Hand-crafted for superb balance, ping response, and lightweight pick-up.',
    price: 6999,
    image: '/images/bat_elite.png',
    category: 'Sports Equipment',
    specifications: {
      'Material': 'Imported English Willow',
      'Grade': 'Grade 1 Professional',
      'Weight': '1170 - 1190g',
      'Grip Type': 'Dynamic Matrix Texture',
      'Sweet Spot': 'Mid Profile Optimal'
    }
  },
  {
    id: 'prod_bat_premium',
    name: 'Cricket Bat Premium',
    description: 'Limited-edition Player Select English Willow bat. Hand-picked for the straightest grains and maximum rebound elasticity. Includes premium padded cover.',
    price: 9999,
    image: '/images/bat_premium.png',
    category: 'Sports Equipment',
    specifications: {
      'Material': 'Player Select English Willow',
      'Grade': 'Grade A+ Reserve',
      'Weight': '1190 - 1210g',
      'Grip Type': 'Octopus Cushioned Pro',
      'Sweet Spot': 'Mid-to-High Profile'
    }
  }
];
