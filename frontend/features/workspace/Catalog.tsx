'use client';

import React, { useState, useEffect } from 'react';
import { useNegotiationState } from '../../hooks/useNegotiationState';
import { mockProducts } from '../../mock/products';
import { apiFetch, IS_DEMO_MODE } from '../../services/api';
import { Tag, Check, Search } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Catalog() {
  const { activeProduct, selectProduct, isTyping } = useNegotiationState();
  const [searchQuery, setSearchQuery] = useState('');
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const fetchProducts = async () => {
      setLoading(true);
      try {
        if (IS_DEMO_MODE) {
          setProducts(mockProducts);
        } else {
          // Fetch backend catalog products (which filters or loads popular items if q is empty)
          const res = await apiFetch<any[]>(`/products/search?q=${searchQuery}`);
          if (active) {
            const mapped = res.map(p => ({
              id: p.external_product_id || p.id,
              name: p.name,
              description: p.description || "B2B catalog product under negotiation terms.",
              price: p.selling_price,
              image: `/images/${p.external_product_id}.png`,
              category: p.category,
              specifications: {
                'Category': p.category,
                'Stock': `${p.stock_quantity} units`,
                'Popularity': `${(p.popularity_index / 20.0).toFixed(1)}/5.0`,
                'Return Rate': `${p.return_rate.toFixed(2)}%`
              }
            }));
            setProducts(mapped);
          }
        }
      } catch (err) {
        console.error("Failed to fetch catalog search results", err);
      } finally {
        if (active) setLoading(false);
      }
    };
    
    // Simple debounce/delay to prevent spamming queries
    const delayDebounceFn = setTimeout(() => {
      fetchProducts();
    }, 200);

    return () => {
      active = false;
      clearTimeout(delayDebounceFn);
    };
  }, [searchQuery]);

  return (
    <div className="glass-panel rounded-xl p-5 flex flex-col h-full min-h-0">
      
      {/* Title */}
      <div className="flex items-center space-x-2 border-b border-white/10 pb-3 mb-4">
        <Tag className="h-4 w-4 text-cyan-glow" />
        <span className="font-mono text-xs font-bold tracking-widest text-white/80 uppercase">
          B2B Product Catalog
        </span>
      </div>

      {/* Search Bar */}
      <div className="relative mb-4">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search products (e.g. cricket bat)"
          className="w-full bg-black/40 border border-white/10 rounded-lg pl-3 pr-8 py-2 text-xs font-mono text-white placeholder-white/30 focus:outline-none focus:border-cyan-glow/50 focus:shadow-[0_0_10px_rgba(0,242,254,0.05)] transition-all"
        />
        <Search className="absolute right-2.5 top-2.5 h-3.5 w-3.5 text-white/30" />
      </div>

      {/* Description */}
      <p className="text-[10px] text-white/40 font-mono uppercase tracking-wider mb-4 leading-relaxed">
        Select a product to initialize deal terms
      </p>

      {/* Product List */}
      <div className="space-y-4 overflow-y-auto flex-1 pr-1">
        {loading ? (
          <div className="flex flex-col justify-center items-center py-10">
            <span className="animate-spin h-5 w-5 border-2 border-cyan-glow border-t-transparent rounded-full mb-3"></span>
            <span className="font-mono text-[10px] text-white/30 uppercase tracking-widest">
              Searching...
            </span>
          </div>
        ) : products.length > 0 ? (
          products.map((product) => {
            const isSelected = activeProduct.id === product.id;

            return (
              <motion.div
                key={product.id}
                onClick={() => !isTyping && selectProduct(product.id)}
                className={`rounded-xl border p-4 cursor-pointer transition-all ${
                  isSelected
                    ? 'border-cyan-glow bg-cyan-glow/[0.02] shadow-[0_0_12px_rgba(0,242,254,0.08)]'
                    : 'border-white/5 bg-black/30 hover:border-white/20'
                } ${isTyping ? 'opacity-50 cursor-not-allowed' : ''}`}
                whileHover={{ scale: isTyping ? 1 : 1.01 }}
                transition={{ duration: 0.2 }}
              >
                {/* Product Header */}
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-mono text-xs font-bold text-white tracking-wide uppercase">
                    {product.name}
                  </h3>
                  <span className={`font-mono text-xs font-bold ${isSelected ? 'text-cyan-glow' : 'text-white/60'}`}>
                    ₹{product.price.toLocaleString()}
                  </span>
                </div>

                {/* Description */}
                <p className="text-[11px] text-white/50 font-sans leading-relaxed mb-3">
                  {product.description}
                </p>

                {/* Specifications list */}
                <div className="border-t border-white/5 pt-3 mt-1 space-y-1.5 font-mono text-[9px]">
                  {Object.entries(product.specifications as Record<string, string>).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="text-white/40 uppercase">{key}</span>
                      <span className="text-white/80 font-bold">{value as string}</span>
                    </div>
                  ))}
                </div>

                {/* Selection Badge */}
                {isSelected && (
                  <div className="mt-3.5 flex items-center justify-center space-x-1 rounded bg-cyan-glow/10 border border-cyan-glow/20 py-1 font-mono text-[9px] text-cyan-glow font-bold uppercase">
                    <Check className="h-3 w-3" />
                    <span>ACTIVE CONTRACT TARGET</span>
                  </div>
                )}
              </motion.div>
            );
          })
        ) : (
          <div className="text-center py-10 font-mono text-[10px] text-white/30 uppercase tracking-widest">
            No products found
          </div>
        )}
      </div>

    </div>
  );
}
